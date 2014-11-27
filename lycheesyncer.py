# -*- coding: utf-8 -*-

import sys
import time
import logging
from watchdog.observers import Observer
from galleryhandler import GalleryHandler
import os
import shutil
import stat
import traceback
from lycheedao import LycheeDAO
from lycheemodel import LycheePhoto
from PIL import Image


class LycheeSyncer:

    """
    This class contains the logic behind this program
    It consist mainly in filesystem operations
    It relies on:
    - LycheeDAO for dtabases operations
    - LycheePhoto to store (and compute) photos propreties
    """

    conf = {}

    def __init__(self, conf):
        """
        Takes a dictionnary of conf as input
        """
        self.conf = conf

    def getAlbumNameFromPath(self, path):
        """
        build a lychee compatible albumname from an albumpath (relative to the srcdir main argument)
        Returns a string, the lychee album name
        """
        # make a list with directory and sub dirs
        path = path.split(os.sep)
        # join the rest: no subfolders in lychee yet
        return "_".join(path).lower()

    def isAPhoto(self, file):
        """
        Determine if the filename passed is a photo or not based on the file extension
        Takes a string  as input (a file name)
        Returns a boolean
        """
        validimgext = ['.jpg', '.jpeg', '.gif', '.png']
        ext = os.path.splitext(file)[-1].lower()
        return (ext in validimgext)

    def albumExists(self, album_name):
        """
        Returns an albumid or None if album does not exists
        """
        self.dao.albumExists(self, album_name)

    def createAlbum(self, album_name):
        """
        Creates an album
        Returns an albumid or None if album does not exists
        """
        album = {}
        if album_name != "":
            album['name'] = album_name
            album['id'] = self.dao.createAlbum(album)
        return album['id']

    def thumbIt(self, res, photo, destinationpath, destfile):
        """
        Create the thumbnail of a given photo
        Parameters:
        - res: should be a set of h and v res (640, 480)
        - photo: a valid LycheePhoto object
        - destinationpath: a string the destination full path of the thumbnail (without filename)
        - destfile: the thumbnail filename
        Returns the fullpath of the thuumbnail
        """

        if photo.width > photo.height:
            delta = photo.width - photo.height
            left = int(delta / 2)
            upper = 0
            right = int(photo.height + left)
            lower = int(photo.height)
        else:
            delta = photo.height - photo.width
            left = 0
            upper = int(delta / 2)
            right = int(photo.width)
            lower = int(photo.width + upper)

        destimage = os.path.join(destinationpath, destfile)
        img = Image.open(photo.srcfullpath)
        img = img.crop((left, upper, right, lower))
        img.thumbnail(res, Image.ANTIALIAS)
        img.save(destimage, quality=99)
        return destimage

    def makeThumbnail(self, photo):
        """
        Make the 2 thumbnails needed by Lychee for a given photo
        and store their path in the LycheePhoto object
        Parameters:
        - photo: a valid LycheePhoto object
        returns nothing
        """
        # set  thumbnail size
        sizes = [(200, 200), (400, 400)]
        # insert @2x in big thumbnail file name
        filesplit = os.path.splitext(photo.url)
        destfiles = [photo.url, ''.join([filesplit[0], "@2x", filesplit[1]]).lower()]
        # compute destination path
        destpath = os.path.join(self.conf["lycheepath"], "uploads", "thumb")
        # make thumbnails
        photo.thumbnailfullpath = self.thumbIt(sizes[0], photo, destpath, destfiles[0])
        photo.thumbnailx2fullpath = self.thumbIt(sizes[1], photo, destpath, destfiles[1])

    def addFileToAlbum(self, photo):
        """
        add a file to an album, the albumid must be previously stored in the LycheePhoto parameter
        Parameters:
        - photo: a valid LycheePhoto object
        Returns True if everything went ok
        """
        res = False

        try:
            # copy photo
            if self.conf['link']:
                os.symlink(photo.srcfullpath, photo.destfullpath)
            else:
                shutil.copy(photo.srcfullpath, photo.destfullpath)
            # adjust right (chmod/chown)
            os.lchown(photo.destfullpath, self.conf['uid'], self.conf['gid'])

            if not(self.conf['link']):
                st = os.stat(photo.destfullpath)
                os.chmod(photo.destfullpath, st.st_mode | stat.S_IRWXU | stat.S_IRWXG)
            else:
                st = os.stat(photo.srcfullpath)
                os.chmod(photo.srcfullpath, st.st_mode | stat.S_IROTH)

            res = self.dao.addFileToAlbum(photo)

        except Exception:
            print "addFileToAlbum", Exception
            traceback.print_exc()
            res = False

        return res

    def deleteFiles(self, filelist):
        """
        Delete files in the Lychee file tree (uploads/big and uploads/thumbnails)
        Give it the file name and it will delete relatives files and thumbnails
        Parameters:
        - filelist: a list of filenames
        Returns nothing
        """

        for url in filelist:
            if self.isAPhoto(url):
                thumbpath = os.path.join(self.conf["lycheepath"], "uploads", "thumb", url)
                filesplit = os.path.splitext(url)
                thumb2path = ''.join([filesplit[0], "@2x", filesplit[1]]).lower()
                thumb2path = os.path.join(self.conf["lycheepath"], "uploads", "thumb", thumb2path)
                bigpath = os.path.join(self.conf["lycheepath"], "uploads", "big", url)

                os.remove(thumbpath)
                os.remove(thumb2path)
                os.remove(bigpath)

    def rotatephoto(self, photo, rotation):
        # rotate main photo
        img = Image.open(photo.destfullpath)
        img2 = img.rotate(rotation)
        img2.save(photo.destfullpath, quality=99)
        # rotate Thumbnails
        img = Image.open(photo.thumbnailx2fullpath)
        img2 = img.rotate(rotation)
        img2.save(photo.thumbnailx2fullpath, quality=99)
        img = Image.open(photo.thumbnailfullpath)
        img2.rotate(rotation)
        img2.save(photo.thumbnailfullpath, quality=99)

    def adjustRotation(self, photo):
        """
        Rotates photos according to the exif orienttaion tag
        Returns nothing
        """
        if photo.exif.orientation not in (0, 1):
            # There is somthing to do
            if photo.exif.orientation == 6:
                # rotate 90° clockwise
                # AND LOOSE EXIF DATA
                self.rotatephoto(photo, -90)
            if photo.exif.orientation == 8:
                # rotate 90° counterclockwise
                # AND LOOSE EXIF DATA
                self.rotatephoto(photo, 90)

    def reorderalbumids(self, albums):

        # sort albums by title
        def getName(album):
            return album['name']

        sortedalbums = sorted(albums, key=getName)

        # count albums
        nbalbum = len(albums)
        # get higher album id + 1 as a first new album id
        min, max = self.dao.getAlbumMinMaxIds()

        if nbalbum + 1 < min:
            newid = 1
        else:
            newid = max + 1

        for a in sortedalbums:
            self.dao.changeAlbumId(a['id'], newid)
            newid = newid + 1

    def updateAlbumsDate(self, albums):
        for a in albums:
            try:
                datelist = [photo.sysdate for photo in a['photos']]
                if datelist is not None and len(datelist) > 0:
                    maxdate = max(datelist)
                    self.dao.updateAlbumDate(a['id'], maxdate.replace(':', '-'))
            except Exception as e:
                print "ERROR: updating album date for album:" + a['name'], e

    def deleteAllFiles(self):
        """
        Deletes every photo file in Lychee
        Returns nothing
        """
        filelist = []
        photopath = os.path.join(self.conf["lycheepath"], "uploads", "big")
        filelist = [f for f in os.listdir(photopath)]
        self.deleteFiles(filelist)

    def sync(self):
        self.dao = LycheeDAO(self.conf)

        path = self.conf["srcdir"]
        event_handler = GalleryHandler(self)
        observer = Observer()
        observer.schedule(event_handler, path, recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
