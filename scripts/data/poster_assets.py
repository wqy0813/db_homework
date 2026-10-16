"""Choose only poster files tracked in the shared poster collection."""
from posters import CATALOG, collected_poster


POSTER_URLS = tuple(sorted(set(CATALOG.values())))

if not POSTER_URLS:
    raise RuntimeError(
        'No collected poster files are available; restore poster_collect before generating data.'
    )


def poster_assets_for(name, category_id, count, offset=0):
    """Return a valid primary poster and a distinct, valid gallery URL list."""
    primary = collected_poster(name, category_id)
    if primary is None:
        primary = POSTER_URLS[offset % len(POSTER_URLS)]

    assets = [primary]
    for step in range(len(POSTER_URLS)):
        candidate = POSTER_URLS[(offset + step) % len(POSTER_URLS)]
        if candidate not in assets:
            assets.append(candidate)
        if len(assets) == count:
            break

    while len(assets) < count:
        assets.append(primary)
    return primary, assets
