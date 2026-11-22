"""Plan all registered Yui works once without clobbering another batch."""
import re

BASELINE = frozenset(('artgravia-693-yui-public-samples', 'artgravia-639-yui-public-samples',
    'artgravia-650-yui-public-samples', 'artgravia-670-yui-public-samples',
    'artgravia-677-yui-public-samples', 'artgravia-684-yui-public-samples',
    'yui-asuna-qipao-public-samples', 'yui-become-beautiful-public-samples',
    'yui-meow-public-samples', 'yui-night-cat-public-samples',
    'yui-night-training-public-samples', 'yui-pure-public-samples', 'yui-summer-public-samples'))


def plan(registry, batch_size=8):
    if not 1 <= batch_size <= 8:
        raise ValueError('INVALID_BATCH_BOUND')
    ids = [r.get('id') for r in registry]
    if any(not isinstance(i, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,100}', i) for i in ids):
        raise ValueError('INVALID_REGISTERED_WORK')
    if len(set(ids)) != len(ids) or not BASELINE <= set(ids):
        raise ValueError('DUPLICATE_OR_MISSING_BASELINE_WORK')
    groups = {'showart': [], 'independent': []}
    for row in registry:
        kind = 'showart' if row.get('source', '').startswith('https://showartx.net/') else 'independent'
        groups[kind].append(row['id'])
    if len(groups['independent']) < 4:
        raise ValueError('INDEPENDENT_SOURCE_BASELINE_MISSING')
    return [{'stage': f'{kind}-{offset//batch_size+1:03d}', 'kind': kind,
             'ids': values[offset:offset+batch_size]}
            for kind, values in groups.items() for offset in range(0, len(values), batch_size)]
