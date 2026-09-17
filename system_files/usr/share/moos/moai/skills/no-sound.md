---
id: no-sound
title_en: No sound, or sound from the wrong device
title_ar: لا يوجد صوت، أو الصوت يخرج من جهاز خاطئ
use_when: The person hears nothing, sound is very quiet, crackles, or plays through the wrong speakers or headset.
---
## Look first
1. `get_system_status` — read the volume and the mute state. Muted, or a volume under 10, explains most "no sound" reports.
2. `unit_status` name=`pipewire.service` user=true, then `wireplumber.service` and `pipewire-pulse.service` the same way. All three must be active (running).
3. If one of them is failed or keeps restarting: `read_journal` unit=<that unit> user=true priority=`warning` since=`boot` lines=60.

## Steps
1. Muted → `set_mute` value=`unmute`. Volume low → `set_volume` value=`60`. Ask the person to play something.
2. A sound service has failed, or all three look healthy and there is still no sound → `fix_audio`. It asks the person first, then restarts the sound services; an app that was playing may need to be reopened.
3. After `fix_audio`, check the three services again with `unit_status` and say what changed.
4. Sound works but comes from the wrong place (an HDMI monitor, a headset) → `open_settings` page=`audio` and tell the person to choose the output device there. No tool chooses the device for them.
5. A Bluetooth headset is connected but silent → read skill `bluetooth-device`.

## Stop and tell the person when
- The three services are active, the volume is up and the right device is selected, and there is still no sound: say exactly that, offer `support_bundle`, and do not run `fix_audio` a second time.
- The log says no sound card was found: this is hardware or firmware, not settings → `check_drivers`.
