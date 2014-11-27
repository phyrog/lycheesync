from watchdog.events import FileSystemEventHandler
from lycheemodel import LycheePhoto
import os

class GalleryHandler(FileSystemEventHandler):

    def __init__(self, syncer):
        super(GalleryHandler, self)
        self.syncer = syncer
    
    def on_created(self, event):
        super(GalleryHandler, self).on_created(event)
        if self.syncer.isAPhoto(event.src_path):
            album = {}
            album['path'] = os.path.dirname(event.src_path)
            album['relpath'] = os.path.relpath(album['path'], self.syncer.conf['srcdir'])
            album['name'] = self.syncer.getAlbumNameFromPath(album['relpath'])
            album['id'] = self.syncer.createAlbum(album['name'])
            photo = LycheePhoto(self.syncer.conf, os.path.basename(event.src_path), album)
            self.syncer.makeThumbnail(photo)
            self.syncer.addFileToAlbum(photo)
            self.syncer.adjustRotation(photo)

    def on_deleted(self, event):
        super(GalleryHandler, self).on_deleted(event)
        if self.syncer.isAPhoto(event.src_path):
            album = {}
            album['path'] = os.path.dirname(event.src_path)
            album['relpath'] = os.path.relpath(album['path'], self.syncer.conf['srcdir'])
            album['name'] = self.syncer.getAlbumNameFromPath(album['relpath'])
            album['id'] = self.syncer.createAlbum(album['name'])
            self.syncer.dao.erasePhoto(os.path.basename(event.src_path), album['id'])
        else:
            album = {}
            album['path'] = event.src_path
            album['relpath'] = os.path.relpath(album['path'], self.syncer.conf['srcdir'])
            album['name'] = self.syncer.getAlbumNameFromPath(album['relpath'])
            album['id'] = self.syncer.createAlbum(album['name'])
            self.syncer.dao.eraseAlbum(album)
            

    def on_modified(self, event):
        super(GalleryHandler, self).on_modified(event)

    def on_moved(self, event):
        super(GalleryHandler, self).on_moved(event)
