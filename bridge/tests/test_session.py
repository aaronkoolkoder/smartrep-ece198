from smartrep.session import status_for

DOSE = [dict(exercise_id='curl',sets=2,reps_min=10,reps_max=15)]


def row(count=10,good=10,short=0,rushed=0,ended=True):
    return dict(exercise_id='curl',reps_completed=count,good=good,short=short,rushed=rushed,ended_at='now' if ended else None)


def test_status_rules_and_priority():
    assert status_for(DOSE,[]) == 'on_track'
    assert status_for(DOSE,[row()],left_incomplete=True) == 'behind'
    assert status_for(DOSE,[row(count=21)],left_incomplete=True) == 'over_dose'
    assert status_for(DOSE,[row(),row(),row()]) == 'over_dose'
    assert status_for(DOSE,[row(count=7,good=7,short=3)]) == 'form_check'
    assert status_for(DOSE,[row(count=10,good=7,rushed=3)],ready=True) == 'form_check'
    assert status_for(DOSE,[],ready=True) == 'ready_to_progress'
    assert status_for(DOSE,[row(),row()]) == 'done'
    assert status_for(DOSE,[row(),row(count=0,good=0,short=10)]) == 'form_check'
    assert status_for(DOSE,[row(),row(ended=False)]) == 'on_track'
