"""Source-linked English reading diagnostics using the installed spaCy parser."""
import argparse
import json
import re
import statistics
from pathlib import Path
import spacy

PREFERENCE=set('promising pivotal comprehensive transformative intricate paradigm unprecedented underscore landscape holistic revolutionize delve crucial robust notably'.split())

def metrics(nlp,text):
    clean=re.sub(r'\{\{(?:cite|xref):[^{}]+\}\}',lambda m:' '*len(m[0]),text)
    doc=nlp(clean);sentences=[];distances=[];bare=[];nominal=[];preferences=[];beginnings=[];total=0
    for i,s in enumerate(doc.sents,1):
        words=[t for t in s if t.is_alpha];total+=len(words)
        sentences.append(dict(sentence=i,start=s.start_char,end=s.end_char,words=len(words),review_candidate=len(words)>40))
        beginnings.append(words[0].lower_ if words else '')
        for token in s:
            if token.dep_ in ('nsubj','nsubjpass'):
                distance=sum(t.is_alpha for t in doc[min(token.i,token.head.i)+1:max(token.i,token.head.i)])
                distances.append(dict(sentence=i,subject=token.text,predicate=token.head.text,words_between=distance,review_candidate=distance>12))
                if token.lower_ in ('this','these') and token.pos_=='PRON':bare.append(dict(sentence=i,start=token.idx,text=token.text))
            if token.pos_=='NOUN' and token.lower_.endswith(('tion','ment','ance','ence','ity')):nominal.append(dict(text=token.text,start=token.idx))
            if token.lemma_.lower() in PREFERENCE:preferences.append(dict(text=token.text,start=token.idx,sentence=i))
    repeated=[dict(first_sentence=i+1,word=beginnings[i]) for i in range(max(0,len(beginnings)-2)) if beginnings[i] and len(set(beginnings[i:i+3]))==1]
    definitions={m[1]:m.start() for m in re.finditer(r'\(([A-Z][A-Z0-9-]{1,9})\)',clean)}
    abbreviations=[]
    for match in re.finditer(r'\b[A-Z][A-Z0-9-]{1,9}\b',clean):
        if match.start()<definitions.get(match[0],float('inf')):abbreviations.append(dict(text=match[0],start=match.start(),check='term or abbreviation; check definition and shared glossary'))
    lengths=[x['words'] for x in sentences]
    return dict(words=total,sentences=sentences,median_sentence_words=statistics.median(lengths) if lengths else 0,
        subject_predicate_distances=distances,nominalizations=nominal,nominalizations_per_100_words=100*len(nominal)/max(1,total),
        bare_demonstrative_subjects=bare,repeated_sentence_starts=repeated,abbreviation_candidates=abbreviations,
        preference_word_occurrences=preferences,interpretation='Review candidates: resolve with original meaning, paragraph purpose and corpus examples.')

def main():
    p=argparse.ArgumentParser();p.add_argument('--input');p.add_argument('--corpus');p.add_argument('--output',required=True);p.add_argument('--baseline');p.add_argument('--model',default='en_core_web_sm');a=p.parse_args()
    nlp=spacy.load(a.model);metadata=dict(spacy=spacy.__version__,model=a.model,model_version=nlp.meta['version'])
    if a.corpus:
        chunks=[json.loads(line) for line in Path(a.corpus).read_text(encoding='utf-8').splitlines() if line.strip()]
        records=[dict(chunk_id=x['chunk_id'],paper_id=x['paper_id'],metrics=metrics(nlp,x['text_clean'])) for x in chunks]
        values=sorted(x['metrics']['nominalizations_per_100_words'] for x in records)
        result=dict(parser=metadata,paragraphs=len(records),nominalizations_p75=values[int(.75*(len(values)-1))],records=records)
    else:
        result=dict(parser=metadata,metrics=metrics(nlp,Path(a.input).read_text(encoding='utf-8')))
        if a.baseline:
            baseline=json.loads(Path(a.baseline).read_text(encoding='utf-8'));threshold=baseline['nominalizations_p75']
            result['corpus_comparison']=dict(nominalizations_p75=threshold,above_p75=result['metrics']['nominalizations_per_100_words']>threshold,source=a.baseline)
    output=Path(a.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),parser=metadata,paragraphs=result.get('paragraphs')),ensure_ascii=False))

if __name__=='__main__':main()
