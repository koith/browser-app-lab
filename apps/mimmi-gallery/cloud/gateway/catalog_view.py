"""Public viewer metadata, without private paths or source correspondence."""


def gallery_catalog(catalog):
    albums=[]
    for album in catalog['albums']:
        view={key:album[key] for key in ('id','title','publisher','expected') if key in album}
        images=[]
        for photo in album.get('images',[]):
            image={key:photo[key] for key in ('number','sha256','bytes','width','height',
                'preview_sha256','display_rotation') if key in photo}
            if photo.get('preview'):image['preview']=True
            images.append(image)
        view['images']=images;albums.append(view)
    return {'schema_version':catalog['schema_version'],'model':catalog['model'],
            'storage':'sha-verified-owner-metadata-only','albums':albums}
