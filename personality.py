"""Causal personality-state proxies. Coefficients are engineered, not human fits."""
import math
import human_dynamics

DISPOSITIONS = ('emotional_regulation','negative_bias','positive_bias',
                'uncertainty_tolerance','impulsivity','delay_discounting',
                'attachment_security','assertiveness','achievement_drive',
                'altruism','self_compassion','routine_preference') + tuple(human_dynamics.FACETS)
NEEDS = ('safety','self_worth','autonomy','competence','belonging')


def bound(value):
    return max(0.0,min(1.0,value))


def initialize(state, traits):
    # Deterministic engineering defaults preserve the existing genome mapping.
    defaults = dict(zip(DISPOSITIONS, (
        (traits['recovery']+traits['attention'])/2, traits['threat_sensitivity'],
        traits['reward_sensitivity'], 1-traits['caution'], 1-traits['planning'],
        1-traits['persistence'], traits['trust_prior'], traits['persistence'],
        traits['persistence'], traits['cooperation'], traits['recovery'], 1-traits['novelty_preference'])))
    state.setdefault('personality',{'dispositions':defaults,'baseline':dict(defaults),
                                  'updates':0,'source':'engineered_defaults_not_psychometric_measurements'})
    state.setdefault('psychological_needs',{name:0.5 for name in NEEDS})
    state.setdefault('appraisal',{'novelty':0.0,'goal_congruence':0.0,
                                'controllability':0.5,'social_acceptance':0.5})
    state.setdefault('behavior_repetition',{})
    human_dynamics.initialize(state,traits)


def fatigue(state):
    body=state.get('body',{})
    return bound(0.5*(1-state['energy'])+0.3*body.get('sleep_pressure',0)+0.2*state['stress'])


def bias(scores,state):
    p=state.get('personality',{}).get('dispositions')
    if not p:
        return
    n=state['psychological_needs']
    tired=fatigue(state)
    fear=state.get('affect',{}).get('fear',0)
    scores['rest']+=0.4*tired+0.2*p['self_compassion']*(1-n['self_worth'])
    scores['reflect']+=0.3*p['emotional_regulation']*state['stress']
    scores['explore']+=0.2*(1-n['autonomy'])*p['assertiveness']-0.3*(1-n['safety'])*(1-p['uncertainty_tolerance'])
    scores['practice']+=0.3*p['achievement_drive']*(1-n['competence'])-0.2*tired
    scores['help']+=0.25*p['altruism']-0.2*(1-p['assertiveness'])*fear
    scores['socialize']+=0.3*(1-n['belonging'])*p['attachment_security']-0.15*fear*(1-p['attachment_security'])
    repetitions=state.get('behavior_repetition',{})
    for action in scores:
        repeated=min(1,repetitions.get(action,0)/5)
        scores[action]+=0.15*(2*p['routine_preference']-1)*repeated


def update(state,traits,outcome):
    initialize(state,traits)
    p=state['personality']['dispositions']
    n=state['psychological_needs']
    action,reward=outcome['action'],outcome['reward']
    count=state['behavior_repetition'].get(action,0)
    novelty=1/(1+count)
    for previous in list(state['behavior_repetition']):
        state['behavior_repetition'][previous]*=0.9
    state['behavior_repetition'][action]=count*0.9+1
    acceptance=(1 if outcome.get('trust_delta',0)>0 else 0) if outcome.get('partner_id') else 0.5
    model=state.get('world_model',{}).get(action,{})
    controllability=bound(0.5+0.5*model.get('reward_mean',0))
    state['appraisal']={'novelty':novelty,'goal_congruence':reward,
                        'controllability':controllability,'social_acceptance':acceptance}
    for name in NEEDS:
        n[name]+=0.01*(0.5-n[name])-0.005
    n['safety']+=0.04*reward if action=='explore' else 0.01*(1-state['stress'])
    n['self_worth']+=0.04*reward*(1-0.7*p['self_compassion'] if reward<0 else 1)
    if action=='practice':n['competence']+=0.04*max(0,reward)
    if action=='explore':n['autonomy']+=0.03
    if outcome.get('partner_id'):n['belonging']+=0.06*(2*acceptance-1)
    for name in NEEDS:n[name]=bound(n[name])
    affect=state['affect']
    # Regulation dampens sustained arousal/fear; bias changes experienced proxy valence.
    affect['fear']*=1-0.15*p['emotional_regulation']
    affect['frustration']*=1-0.2*p['emotional_regulation']
    affect['valence']=max(-1,min(1,affect['valence']+0.05*reward*(p['positive_bias'] if reward>=0 else p['negative_bias'])))
    # Slow experience changes, with a weak baseline pull; never changes inherited DNA.
    targets={'attachment_security':acceptance,'achievement_drive':controllability,
             'uncertainty_tolerance':1 if reward>=0 else 0,
             'self_compassion':1-state['stress']}
    for name,target in targets.items():
        rate=0.005*traits['plasticity']
        p[name]=bound(p[name]+rate*(target-p[name])+0.0005*(state['personality']['baseline'][name]-p[name]))
    state['personality']['updates']+=1


def configure(state,dispositions,source='supplied_configuration'):
    if not isinstance(dispositions,dict) or not dispositions or set(dispositions)-set(DISPOSITIONS):
        raise ValueError('Provide known disposition names')
    if any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in dispositions.values()):
        raise ValueError('Disposition values must be finite numbers in [0,1]')
    if not isinstance(source,str) or not 1<=len(source)<=200:
        raise ValueError('source must contain 1–200 characters')
    for name,value in dispositions.items():
        state['personality']['dispositions'][name]=value
        state['personality']['baseline'][name]=value
    state['personality']['source']=source
    return state['personality']


def inventory(state=None):
    import genome
    import brain
    import engine
    result={'inherited_trait_count':len(genome.TRAITS),'inherited_traits':list(genome.TRAITS),
            'developing_disposition_count':len(DISPOSITIONS),'developing_dispositions':list(DISPOSITIONS),
            'named_trait_controls':len(genome.TRAITS)+len(DISPOSITIONS),
            'psychological_need_count':len(NEEDS),'psychological_needs':list(NEEDS),
            'brain_modules':len(brain.REGIONS),'synthetic_routes':len(brain.EDGES),
            'brain_control_parameters':len(brain.PARAMETERS),'actions':len(engine.ACTIONS),
            'simulated_skill_counters':len(engine.SKILLS),'appraisal_dimensions':len(human_dynamics.APPRAISALS),
            'affect_variables':4+len(human_dynamics.EMOTIONS),
            'body_drives':3,'facet_mechanisms':{k:{'action':v[0],'signal':v[2]} for k,v in human_dynamics.FACETS.items()},
            'human_fidelity_measured':False,
            'interpretation':'Named engineering controls; not independent, validated human traits or biological genes.'}
    if state is not None:
        def leaves(obj,prefix=''):
            if isinstance(obj,dict):
                return [path for key,value in obj.items() for path in leaves(value,prefix+'.'+key if prefix else key)]
            if isinstance(obj,list):
                return [path for i,value in enumerate(obj) for path in leaves(value,f'{prefix}[{i}]')]
            return [prefix] if type(obj) in (int,float) else []
        paths=leaves(state)
        result['stored_numeric_state_values']=len(paths)
        result['numeric_state_paths']=paths
        result['state_count_scope']='Includes counters, baseline copies, cached activities and learned weights. Grows with experience; not a trait count.'
    return result
