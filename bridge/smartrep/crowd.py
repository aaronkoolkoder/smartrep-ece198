"""Optional demo participants use real sessions and the real detector."""
import asyncio
from .session import SessionError


class Crowd:
    def __init__(self,manager):
        self.manager=manager
        self.task=None

    @property
    def running(self):
        return self.task is not None and not self.task.done()

    async def set_enabled(self,enabled):
        if enabled and not self.running:
            self.task=asyncio.create_task(self.run())
        elif not enabled and self.task:
            self.task.cancel()
            await asyncio.gather(self.task,return_exceptions=True)
            self.task=None

    async def run(self):
        # Mary's 5 lb station stays free for the person demonstrating the app.
        assignments=[('204417','db-3lb'),('118560','db-8lb'),('150093','glove-1'),('311802','db-3lb')]
        own_sets=[]
        try:
            while assignments:
                for participant,station in assignments:
                    if any(s['participant_id']==participant for s in self.manager.active.values()):
                        continue
                    exercise='wall-push-up' if station=='glove-1' else 'bicep-curl'
                    today=self.manager.today_data(participant)
                    dose=next(d for d in today['dose'] if d['exercise_id']==exercise)
                    if sum(s['exercise_id']==exercise for s in today['sets'])>=dose['sets']:
                        continue
                    try:
                        device=next(d['device_id'] for d in self._stations() if d['id']==station)
                        self.manager.source.set_pattern(device,'mixed' if participant=='204417' else 'good')
                        result=await self.manager.start(participant,station,exercise)
                        own_sets.append(result['set_id'])
                    except SessionError:
                        pass
                if not own_sets:
                    return
                for _ in range(45):
                    await asyncio.sleep(1)
                    for set_id in list(own_sets):
                        row=self.manager.detail(set_id)
                        if row['ended_at'] or row['reps_completed']>=10:
                            await self.manager.finish(set_id)
                            own_sets.remove(set_id)
                    if not own_sets:
                        break
                for set_id in list(own_sets):
                    await self.manager.finish(set_id)
                    own_sets.remove(set_id)
                assignments=[(p,s) for p,s in assignments if sum(x['exercise_id']==('wall-push-up' if s=='glove-1' else 'bicep-curl') for x in self.manager.today_data(p)['sets'])<2]
                await asyncio.sleep(4)
        finally:
            for set_id in own_sets:
                await self.manager.finish(set_id)

    def _stations(self):
        from .db import connect
        with connect(self.manager.path) as db:
            return [dict(x) for x in db.execute('SELECT * FROM stations')]
