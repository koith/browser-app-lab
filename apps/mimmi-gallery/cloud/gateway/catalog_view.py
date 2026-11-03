"""Public viewer metadata, without private paths or source correspondence."""


def gallery_catalog(catalog):
    albums=[]
    for album in catalog['albums']:
        view={key:album[key] for key in ('id','title','publisher','expected') if key in album}
        images=[]
        for photo in album.get('images',[]):
            image={key:photo[key] for key in ('number','sha256','bytes','width','height',
                'preview_sha256','display_rotation') if key in photo}
            if photo.get('preview'):
                image['preview']=True
                # Preview size is public, non-sensitive integrity metadata.
                # The live gateway already requires this for a verified SHA
                # read; without it browser QA cannot validate actual bytes.
                preview_bytes=photo.get('preview_bytes')
                if type(preview_bytes) is int and 0 < preview_bytes <= 35_000_000:
                    image['preview_bytes']=preview_bytes
            # Export only bounded, non-sensitive quality provenance fields,
            # never private storage keys or source URLs.
            if photo.get('watermark_status') in ('present_verified','absent_verified'):
                image['watermark_status']=photo['watermark_status']
            q=photo.get('visual_quality')
            if isinstance(q,dict) and q.get('method')=='paired-decoded-pixel-v1' and q.get('confidence')=='measured' and q.get('same_photo_verified') is True and q.get('relation') in ('higher','lower','comparable') and isinstance(q.get('compared_to_sha256'),str) and len(q['compared_to_sha256'])==64 and all(c in '0123456789abcdef' for c in q['compared_to_sha256']):
                image['visual_quality']={key:q[key] for key in ('method','confidence','same_photo_verified','relation','compared_to_sha256')}
            images.append(image)
        view['images']=images;albums.append(view)
    return {'schema_version':catalog['schema_version'],'model':catalog['model'],
            'storage':'sha-verified-owner-metadata-only','albums':albums}
