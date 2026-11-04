import math
import random
import pytest
from smartrep.units import convert
from smartrep.orientation import Orientation
from smartrep.sources.sim_source import sample_at


def test_unit_scales():
    assert convert(dict(ax=8192,ay=0,az=-8192,gx=655,gy=0,gz=-655),'mpu6050_4g_500dps') == dict(ax=1,ay=0,az=-1,gx=10,gy=0,gz=-10)
    for units,zero,scale in [('counts14',5400,1080),('counts10',338,68)]:
        assert convert(dict(x=zero,y=zero+scale,z=zero-scale),units) == dict(x=0,y=1,z=-1)
    with pytest.raises(ValueError):
        convert({},'unknown')


def test_biased_noisy_curl_orientation():
    orientation = Orientation()
    rng = random.Random(2)
    errors = []
    for index in range(1500):
        seconds = index / 50
        movement = max(0,seconds-.6)
        sample = sample_at(movement,rng)
        angles = orientation.update(index*20,convert(sample,'mpu6050_4g_500dps'))
        if orientation.ready:
            expected = 110*(1-math.cos(2*math.pi*movement/2.5))/2
            errors.append(abs(angles['pitch']-expected))
    assert max(errors) < 5
    assert abs(orientation.bias['gy']-.4) < .02
