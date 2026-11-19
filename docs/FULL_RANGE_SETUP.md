# Full-range exercise setup

The final launcher uses normal full-range hardware mode and `smartrep-hardware.db`.
The small-movement classroom mode remains available only through its separate launcher.
Calibration allows up to 90 seconds for positioning and three controlled movements.

On November 19, the user performed curls and the normal-mode calibration accepted
and saved a bicep-curl reference in the local hardware database. This is a movement
reference, not an independent angle-accuracy or rep-count validation. The first row
recording detected one cycle before timing out; a row reference remains to be recorded.

Keep separate references for curls and bent-over rows. Finish at the starting
position before saving. Recalibrate after changing the sensor mount or exercise.
Raw movement samples and per-person references stay in the ignored local SQLite
database; they are not embedded in the firmware or committed to Git.

Staff setup: patient 123129, demo PIN 0000, choose the exercise, perform three full
movements, then save the reference. Close the diagnostics page before recording.

## Row calibration observation

The user reported the live counter reaching three cycles while reference saving
still returned a retry error. The live counter is provisional; final validation
can reject a different dominant signal or an incomplete return to the starting
position. Recorded attempts include insufficient-cycle and finish-at-start errors.
No successful row reference is claimed. At the user's request, the current logic
is retained without further changes or movement tests.
