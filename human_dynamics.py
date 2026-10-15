"""Inspectable social, affective and motivational proxies; no human-fitted claims."""
import math

# Every control has a causal score contribution plus the specialist paths below.
# Mapping: target action, direction, contextual signal, engineering default source.
FACETS = {
 'learning_progress_drive':('practice',1,'progress','curiosity'),
 'creativity':('create',1,'autonomy','novelty_preference'),
 'diligence':('practice',1,'competence','persistence'),
 'organization':('plan',1,'uncertainty','planning'),
 'perfectionism':('practice',1,'error','attention'),
 'patience':('plan',1,'stress','persistence'),
 'frustration_tolerance':('practice',1,'frustration','recovery'),
 'forgiveness':('repair',1,'resentment','cooperation'),
 'gratitude':('help',1,'gratitude','reciprocity'),
 'fairness':('help',1,'unfairness','cooperation'),
 'generosity':('help',1,'resources','empathy'),
 'modesty':('practice',1,'competence','caution'),
 'social_confidence':('socialize',1,'belonging','sociability'),
 'rejection_sensitivity':('socialize',-1,'rejection','threat_sensitivity'),
 'attachment_anxiety':('socialize',1,'loneliness','trust_prior'),
 'attachment_avoidance':('socialize',-1,'belonging','caution'),
 'sensory_sensitivity':('rest',1,'arousal','threat_sensitivity'),
 'loss_aversion':('explore',-1,'loss','caution'),
 'cognitive_flexibility':('explore',1,'repetition','plasticity'),
 'ambiguity_aversion':('explore',-1,'uncertainty','caution'),
 'self_discipline':('practice',1,'fatigue','persistence'),
 'playfulness':('play',1,'boredom','novelty_preference'),
 'competitiveness':('practice',1,'competence','reward_sensitivity'),
 'deliberation':('plan',1,'uncertainty','planning'),
}
EMOTIONS=('joy','sadness','anger','shame','pride','gratitude','boredom','loneliness')
APPRAISALS=('novelty','goal_congruence','controllability','social_acceptance','agency','fairness','loss')
VERSION=5


def clamp(x):return max(0.0,min(1.0,x))


def initialize(state,traits):
    p=state['personality']
    for name,(_,_,_,origin) in FACETS.items():
        value=traits[origin]
        p['dispositions'].setdefault(name,value)
        p['baseline'].setdefault(name,value)
    p['schema_version']=VERSION
    for name in EMOTIONS:state['affect'].setdefault(name,0.0)
    for name,value in (('agency',0.5),('fairness',0.5),('loss',0.0)):
        state['appraisal'].setdefault(name,value)
    state.setdefault('motivation',{'action_progress':{},'last_error':{},'boredom':0.0})
    state.setdefault('social_dynamics',{})
    state.setdefault('self_narrative',{'milestones':[],'source':'recorded_simulation_events_only'})
    state.setdefault('intentions',{'action':None,'remaining':0,'switches':0})
    state.setdefault('artifacts',[])
    state.setdefault('creative_output_count',max((a['index']+1 for a in state['artifacts']),default=0))
    for action in ('create','play','plan','repair'):state['learned_values'].setdefault(action,0.0)


def signals(state):
    from personality import fatigue
    n=state['psychological_needs']
    a=state['affect']
    bonds=list(state.get('social_dynamics',{}).values())
    mean=lambda key:sum(b[key] for b in bonds)/len(bonds) if bonds else 0.5
    return {'progress':max(state['motivation']['action_progress'].values(),default=0),
            'autonomy':1-n['autonomy'],'competence':1-n['competence'],
            'uncertainty':1-state['confidence'],'error':abs(state['prediction_error']),
            'stress':state['stress'],'frustration':a['frustration'],
            'resentment':mean('resentment'),'gratitude':mean('gratitude'),
            'unfairness':1-state['appraisal'].get('fairness',0.5),
            'resources':min(1,state['resources']/5),'belonging':1-n['belonging'],
            'rejection':1-state['appraisal']['social_acceptance'],'loneliness':a['loneliness'],
            'arousal':a['arousal'],'loss':state['appraisal'].get('loss',0),
            'repetition':min(1,max(state['behavior_repetition'].values(),default=0)/5),
            'fatigue':fatigue(state),'boredom':max(state['motivation']['boredom'],a['boredom'])}


def bias(scores,state):
    if state.get('personality',{}).get('schema_version',0)<VERSION:return
    p=state['personality']['dispositions']
    context=signals(state)
    trace=[]
    for name,(action,direction,signal,_) in FACETS.items():
        # Small baseline ensures active tendencies even when the signal is absent.
        contribution=direction*0.22*p[name]*(0.15+0.85*clamp(context[signal]))
        if action in scores:
            scores[action]+=contribution
            trace.append({'control':name,'action':action,'signal':signal,'influence':contribution})
    scores['play']+=state['affect']['sadness']*0.15
    scores['repair']+=state['affect']['shame']*0.2
    scores['socialize']-=state['affect']['anger']*0.15
    scores['explore']+=state['affect']['joy']*0.1
    scores['practice']+=state['affect']['pride']*0.05
    scores['help']+=state['affect']['gratitude']*0.1
    for action,progress in state['motivation']['action_progress'].items():
        if action in scores:scores[action]+=0.15*p['learning_progress_drive']*progress
    intention=state['intentions']
    if intention['remaining']>0 and intention['action'] in scores:
        scores[intention['action']]+=0.15*p['organization']*(1-p['cognitive_flexibility'])
    return trace


def appraise(state,goal_congruence=0.0,novelty=0.5,controllability=0.5,
             social_acceptance=0.5,agency=0.5,fairness=0.5,loss=0.0):
    values=locals().copy();values.pop('state')
    for key,value in values.items():
        lower=-1 if key=='goal_congruence' else 0
        if type(value) not in (int,float) or not math.isfinite(value) or not lower<=value<=1:
            raise ValueError(f'{key} must be finite in [{lower},1]')
    p=state['personality']['dispositions']
    a=state['affect']
    positive=max(0,goal_congruence);negative=max(0,-goal_congruence)
    rejection=1-social_acceptance
    targets={'joy':positive*(0.5+0.5*p['positive_bias']),
             'sadness':negative*(1-controllability)+loss*p['loss_aversion'],
             'anger':negative*(1-fairness)*(1-agency),
             'shame':negative*agency*(0.5+0.5*p['perfectionism']),
             'pride':positive*agency*(1-0.5*p['modesty']),
             'gratitude':positive*social_acceptance*(1-agency),
             'boredom':1-novelty,'loneliness':rejection*(0.5+0.5*p['attachment_anxiety'])}
    for name,target in targets.items():a[name]=clamp(0.8*a[name]+0.2*target)
    a['fear']=clamp(0.8*a['fear']+0.2*negative*(1-controllability)*p['negative_bias'])
    a['frustration']=clamp(a['frustration']*(1-0.1*p['frustration_tolerance']))
    state['appraisal']=values
    return {'appraisal':dict(values),'affect':dict(a),'scope':'reaction to supplied appraisal; not inferred ground truth or felt emotion'}


def update(state,traits,outcome,memory_id,tick):
    p=state['personality']['dispositions']
    action=outcome['action'];reward=outcome['reward']
    motivation=state['motivation']
    error=abs(state['prediction_error'])
    previous=motivation['last_error'].get(action,error)
    progress=max(0,previous-error)
    motivation['last_error'][action]=error
    old=motivation['action_progress'].get(action,0)
    motivation['action_progress'][action]=0.8*old+0.2*progress
    motivation['boredom']=clamp(0.85*motivation['boredom']+0.15*(1-state['appraisal']['novelty']))
    partner=outcome.get('partner_id')
    accepted=(1 if outcome.get('trust_delta',0)>0 else 0) if partner else 0.5
    appraise(state,goal_congruence=reward,novelty=state['appraisal']['novelty'],
             controllability=state['appraisal']['controllability'],social_acceptance=accepted,
             agency=0.5 if partner else 1.0,fairness=accepted if partner else 0.5,loss=max(0,-reward))
    if partner:
        bond=state['social_dynamics'].setdefault(partner,{'closeness':0.1,'resentment':0.0,'gratitude':0.0,'interactions':0})
        bond['interactions']+=1
        bond['closeness']=clamp(bond['closeness']+0.03*(2*accepted-1))
        bond['resentment']=clamp(bond['resentment']*(1-0.08*p['forgiveness'])+0.08*(1-accepted))
        bond['gratitude']=clamp(0.9*bond['gratitude']+0.1*accepted)
    if abs(reward)>0.3 or action=='create':
        milestones=state['self_narrative']['milestones']
        milestones.append({'tick':tick,'memory_id':memory_id,'action':action,'reward':reward,'text':outcome['text'][:200]})
        state['self_narrative']['milestones']=milestones[-32:]
    intention=state['intentions']
    if intention['action'] not in (None,action):intention['switches']+=1
    intention['remaining']=max(0,intention['remaining']-1) if intention['action']==action else 0
    intention['action']=action
    if action=='plan':
        models=state['world_model']
        options=[name for name in ('practice','explore','create') if name in models]
        target=max(options,key=lambda name:models[name]['reward_mean']) if options else 'practice'
        intention.update(action=target,remaining=1+int(p['organization']*3))


def partner_weight(state,relation):
    p=state['personality']['dispositions']
    bond=state.get('social_dynamics',{}).get(relation['other_id'],{})
    return max(0.01,0.1+relation['trust']+0.3*bond.get('closeness',0)
               -0.3*bond.get('resentment',0)*(1-p['forgiveness']))
