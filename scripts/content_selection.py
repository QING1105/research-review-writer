"""Project the immutable source ledger into the argument selected for this draft.

Semantic relevance and evidence scope are judged by the writer and independent
reviewer. This module validates the recorded choices and derives citation IDs.
"""
from copy import deepcopy


def require(ok, message):
    if not ok:
        raise ValueError(message)


def project(ledger, plan, policy='preserve_all'):
    require(policy in ('argument_first', 'preserve_all'), 'Unknown content policy')
    selection = plan.get('editorial_selection', {})
    require(isinstance(selection, dict), 'editorial_selection must be an object')
    require(set(selection) <= {'omitted_claims', 'citation_merges'}, 'Unknown editorial selection field')
    omissions = selection.get('omitted_claims', [])
    merges = selection.get('citation_merges', [])
    require(isinstance(omissions, list) and isinstance(merges, list), 'Selection decisions must be lists')
    if omissions or merges:
        require(policy == 'argument_first' and plan['level'] in ('L1', 'L2'),
                'Content selection requires argument_first L1/L2; L0 preserves the accepted source')
    claims = {c['claim_id']: c for c in ledger['claims']}
    omitted = set()
    decisions = []
    for item in omissions:
        cid = item['claim_id']
        require(cid in claims and cid not in omitted, 'Unknown or duplicate omitted claim')
        require(item.get('reason', '').strip() and item.get('effect_on_argument', '').strip(),
                'An omission needs its relevance reason and effect on the argument')
        omitted.add(cid)
        decisions.append(dict(decision_id='omit:' + cid, action='omit_claim', **item))
    active = set(claims) - omitted
    require(active, 'Retain substantive content for the requested section')
    selected = [cid for p in plan['paragraphs'] for cid in p['claim_order']]
    require(len(selected) == len(set(selected)) and set(selected) == active,
            'Each retained claim needs one primary position; every omitted claim needs a decision')
    destinations = {cid: p['new_para_id'] for p in plan['paragraphs'] for cid in p['claim_order']}
    projected = deepcopy(ledger)
    projected['claims'] = [c for c in projected['claims'] if c['claim_id'] in active]
    by_id = {c['claim_id']: c for c in projected['claims']}
    for c in by_id.values():
        c['citation_occurrences'] = []
    occurrences = []
    actions = []
    for oc in ledger['citation_occurrences']:
        owners = [cid for cid in active if oc['occurrence_id'] in claims[cid]['citation_occurrences']]
        groups = {}
        for cid in sorted(owners):
            groups.setdefault(destinations[cid], []).append(cid)
        if not groups:
            actions.append(dict(source_occurrence_id=oc['occurrence_id'], action='omitted_with_claims', output_occurrence_ids=[]))
            continue
        if policy == 'preserve_all':
            require(len(groups) == 1, 'Preserved source citation spans multiple planned paragraphs')
        output_ids = []
        for pid, ids in sorted(groups.items()):
            out = deepcopy(oc)
            oid = oc['occurrence_id'] if len(groups) == 1 else oc['occurrence_id'] + '__' + pid
            out.update(occurrence_id=oid, paragraph_id=pid, required_claim_ids=ids,
                       source_occurrence_ids=[oc['occurrence_id']])
            occurrences.append(out)
            output_ids.append(oid)
            for cid in ids:
                by_id[cid]['citation_occurrences'].append(oid)
        actions.append(dict(source_occurrence_id=oc['occurrence_id'], action='split_with_claims' if len(groups) > 1 else 'retained', output_occurrence_ids=output_ids))
    merged_ids = set()
    for i, item in enumerate(merges, 1):
        ids = item.get('occurrence_ids', [])
        require(len(ids) >= 2 and len(ids) == len(set(ids)), 'Merge at least two distinct source occurrences')
        require(item.get('reason', '').strip(), 'Citation merge needs an editorial reason')
        pid = item.get('paragraph_id')
        available = {o['occurrence_id']: o for o in occurrences}
        require(set(ids) <= available.keys() and not set(ids) & merged_ids, 'Unknown or reused merge occurrence')
        source = [available[oid] for oid in ids]
        require(all(o['paragraph_id'] == pid for o in source), 'Merge citations within their supporting paragraph')
        # Identical references can share a citation after the supported claims
        # in one paragraph. Distinct studies keep separate evidence links.
        require(all(o['ref_keys'] == source[0]['ref_keys'] for o in source),
                'Merge identical reference sets; retain distinct evidence sources separately')
        oid = f'MERGED_CIT{i:04}'
        require(oid not in available, 'Merged occurrence ID collision')
        out = deepcopy(source[0])
        supported = sorted({cid for o in source for cid in o['required_claim_ids']})
        source_ids = list(dict.fromkeys(s for o in source for s in o['source_occurrence_ids']))
        out.update(occurrence_id=oid, required_claim_ids=supported, source_occurrence_ids=source_ids)
        occurrences = [o for o in occurrences if o['occurrence_id'] not in ids] + [out]
        for cid in supported:
            by_id[cid]['citation_occurrences'] = list(dict.fromkeys(oid if v in ids else v for v in by_id[cid]['citation_occurrences']))
        for action in actions:
            if set(action['output_occurrence_ids']) & set(ids):
                action['output_occurrence_ids'] = list(dict.fromkeys(oid if v in ids else v for v in action['output_occurrence_ids']))
                action['action'] = 'merged'
        merged_ids.update(ids)
        decisions.append(dict(decision_id=f'merge:{i}', action='merge_citations', output_occurrence_id=oid, **item))
    projected['citation_occurrences'] = occurrences
    return projected, dict(policy=policy, retained_claim_ids=selected, omitted_claim_ids=sorted(omitted),
                           decisions=decisions, citation_actions=actions)


def writer_projection(ledger, plan, pid, policy):
    """Give the writer selected content and only locally relevant exclusions."""
    selected, audit = project(ledger, plan, policy)
    paragraph = next(p for p in plan['paragraphs'] if p['new_para_id'] == pid)
    order = paragraph['claim_order']
    claims = {c['claim_id']: c for c in selected['claims']}
    current = [claims[cid] for cid in order]
    sids = {sid for c in current for sid in c['sids']}
    excluded = [dict(claim_id=c['claim_id'], text_zh=c['text_zh']) for c in ledger['claims']
                if c['claim_id'] in audit['omitted_claim_ids'] and set(c['sids']) & sids]
    return current, [o for o in selected['citation_occurrences'] if o['paragraph_id'] == pid], excluded
