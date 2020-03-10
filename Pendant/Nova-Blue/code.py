import time, math, random
import board, touchio, analogio, digitalio
import neopixel
import adafruit_fancyled.adafruit_fancyled as fancy

# This is the red LED next to the power switch
led = digitalio.DigitalInOut(board.D13)
led.direction = digitalio.Direction.OUTPUT

# DotStart is the single RGB light on the back of the board, by the reset button
# On the Gemma M0 it's connected to the the SPI interface
try:
    import adafruit_dotstar
    dotstar = adafruit_dotstar.DotStar(board.APA102_SCK, board.APA102_MOSI, 1, brightness=1.0, auto_write=True)
except ImportError:
    dotstar = None

# Capacitive touch sensor on pin A0/D1
# This pin can do lots of other things too, but this lets you get a button with no extra hardware
touch_pin = board.A0
touch = touchio.TouchIn(touch_pin)

# NeoPixels are the main lights in the pendant
# There are 14 of them, arranged in two rings of 7
#   Lower ring: Pixels 0-6
#   Upper ring: Pixels 7-13
# Inside each ring:
#   Pixel 0: Center
#   Pixel 1: Above and to the right of center
#   Pixels 2-6: Clockwise around the ring
# The Gemma M0 D0 output supports DMA for Neopixels, but not in Python
# If you swtich to native Arduino try this: https://learn.adafruit.com/dma-driven-neopixels
ring_len = 7
neopixel_len = ring_len * 2
neopixel = neopixel.NeoPixel(board.D0, neopixel_len, brightness=1.0, auto_write=False)
# Noepixels don't light if scaled below this value
neopixel_min = 0.0045

# Analog light sensor GA1A12S202
sensor = analogio.AnalogIn(board.A1)
# The raw analog sample scale is 2^16, but the sensor can't quite use that whole range
# GA1A12S202 can output about 2k to 60k, logarithmic (which is useful, since eyes are also log-ish)
sensor_min = 2000
sensor_max = 60000

def neopixel_limits(value):
    value = min(1.0, value)
    if (value > neopixel_min):
        value = max(neopixel_min, value)
    else:
        value = 0.0
    return value

def scale():
    # Override to full brightnes if the button is pushed
    if (touch.value):
        scale = 1.0
    else:
        # Normalize (0.0 - 1.0)
        scale = (sensor.value - sensor_min) / (sensor_max - sensor_min)
        # Use an exponent to make the scale more sensitive at the low ends
        # Because this value is normalized squaring always makes it smaller (unless you're at 100%)
        scale = scale ** 2
        # Enforce a minimum to avoid blackouts at low ambient light levels
        scale = neopixel_limits(scale)
    return scale

def decay(value, step, rate):
    v = value * (rate ** step)
    return neopixel_limits(v)

def ring_move(start, move):
    target = start + move
    if (target % ring_len == 0):
        if (move < 0):
            target -= 1
        else:
            target -= ring_len - 1
    if (int(target / ring_len) < int(start / ring_len)):
        target += ring_len
    if (target >= neopixel_len):
        target -= ring_len
    if (target < 0):
        target += ring_len
    return target

def ring_center(start):
    return int(start / ring_len) * ring_len

def set_all(color):
    for j in range(0, neopixel_len):
        neopixel[j] = color
    neopixel.show()

def randRGB():
    color = fancy.CHSV(random.uniform(hue_min, hue_max), 1.0, scale())
    return color.pack()

def starburst_init():
    if (dotstar is not None):
        dotstar[0] = (0, 1, 1)
    return {'bright' : False}

def starburst(c):
    # 0.0-1.0, bigger numbers decay slower
    fade_rate = 0.96
    ramp_rate = 0.80
    # Total steps in the fade/ramp
    ramp_steps = 10
    fade_steps = 90
    side_delay = int(ramp_steps * 0.75)

    # Pick a ring pixel other than center
    pixel = None
    while (pixel == None or pixel % ring_len == 0):
        pixel = random.randint(0, neopixel_len - 1)
    pl = ring_move(pixel, -1)
    pr = ring_move(pixel, 1)
    pc = ring_center(pixel)

    # Pick a related set of colors, always full brightness
    color = fancy.CHSV(random.uniform(hue_min, hue_max), 1.0, 1.0)
    color_l = fancy.CHSV(color.hue - 0.08, 0.85, color.value)
    color_r = fancy.CHSV(color.hue + 0.08, color_l.saturation, color_l.value)
    color_c = fancy.CHSV(color.hue, color_l.saturation, color_l.value)

    for i in range(0, (ramp_steps + fade_steps)):
        #  Allow mode switches
        if (mode_switch()):
            return

        # Primary pixel
        if (i <= (ramp_steps + 1)):
            v = decay(color.value, (ramp_steps - i), ramp_rate)
            f = fancy.CHSV(color.hue, color.saturation, v)
            neopixel[pixel] = f.pack()
        elif (i == ((ramp_steps + fade_steps) - 1)):
            neopixel[pixel] = 0
        else:
            v = decay(color.value, i - ramp_steps, fade_rate)
            f = fancy.CHSV(color.hue, color.saturation, v)
            neopixel[pixel] = f.pack()

        # All pixels are primary if the button is pushed (and the mode is locked)
        if (touch.value and locked):
            c['bright'] = True
            set_all(neopixel[pixel])
        elif (c['bright']):
            c['bright'] = False
            set_all(0)
        # Side pixels
        elif (i >= side_delay and i < (ramp_steps + side_delay)):
            v = decay(color.value * 0.25, ramp_steps + side_delay - i, ramp_rate * 0.975)
            cm = fancy.CHSV(color_l.hue, color_l.saturation, v)
            neopixel[ pl ] = cm.pack()
            cm.hue = color_r.hue
            neopixel[ pr ] = cm.pack()
            cm.hue = color_c.hue
            neopixel[ pc ] = cm.pack()
        elif (i < side_delay or i == ((ramp_steps + fade_steps) - 1)):
            neopixel[ pl ] = 0
            neopixel[ pr ] = 0
            neopixel[ pc ] = 0
        else:
            v = decay(color.value * 0.25, i - side_delay, fade_rate * 0.975)
            cm = fancy.CHSV(color_l.hue, color_l.saturation, v)
            neopixel[ pl ] = cm.pack()
            cm.hue = color_r.hue
            neopixel[ pr ] = cm.pack()
            cm.hue = color_c.hue
            neopixel[ pc ] = cm.pack()

        # Push to hardware
        neopixel.show()
        time.sleep(random.uniform(0.01125, 0.0225))
    time.sleep(random.uniform(0.5, 1.0))

def nextBlue(c):
    hue = random.uniform(hue_min, hue_max)
    value = random.random()
    chaos = random.random()
    if (chaos >= 0.35):
        value /= 12.5;
    value = neopixel_limits(value * scale())
    color = fancy.CHSV(hue, 1.0, value)
    return color

def blue_init():
    if (dotstar is not None):
        dotstar[0] = (0, 0, 1)
    c = { 'current' : {}, 'next' : {}, 'timer' : 0 }
    for j in range(0, neopixel_len):
        c['current'][j] = 0
        c['next'][j] = 0
    return c

def blue(c):
    if (time.monotonic() > c['timer']):
        c['timer'] = time.monotonic() + 0.75
        pixel = random.randint(0, neopixel_len - 1)
        c['current'][pixel] = c['next'][pixel]
        c['next'][pixel] = nextBlue(c)
    for j in range(0, neopixel_len):
        c['current'][j] = fancy.mix(c['current'][j], c['next'][j], 1/25)
        neopixel[j] = c['current'][j].pack()
    neopixel.show()

def sparks_init():
    if (dotstar is not None):
        dotstar[0] = (1, 0, 1)

def sparks(c):
    pixel = random.randint(0, neopixel_len - 1)
    neopixel[pixel] = randRGB()
    neopixel.show()
    # Unset, so the pixel is blank in the next round
    neopixel[pixel] = 0
    time.sleep(0.025)

# Disabled due to low memory on the GemmaM0
#def wheels_init():
#    if (dotstar is not None):
#        dotstar[0] = (1, 0, 0)
#    return {'wheel_offset' : 0}
#
#def wheels(c):
#    for j in range(0, ring_len):
#        if (j % ring_len == 0):
#            neopixel[j] = 0
#            neopixel[j +ring_len] = 0
#        elif ((j + c['wheel_offset']) % 3 == 0):
#            neopixel[neopixel_len - j] = randRGB()
#            neopixel[j] = randRGB()
#        else:
#            neopixel[neopixel_len - j] = 0
#            neopixel[j] = 0
#    neopixel.show()
#    c['wheel_offset'] =  (c['wheel_offset'] + 1) % 3
#    time.sleep(0.065)

def white_init():
    if (dotstar is not None):
        dotstar[0] = (255, 255, 255)
    set_all((255, 255, 255))

def mode_switch():
    global locked
    global last_time
    global mode
    global config

    # Register touch on the LED
    led.value = touch.value

    # Bypass if already locked
    if (locked):
        return

    # Lock the mode after a while
    now = time.monotonic()
    if (now > last_time + timeout):
        locked = True
        return

    # Process mode switching
    change = False
    if (mode < 0):
        change = True
        mode = 0
    if (touch.value):
        if (now > last_time + touch_timeout):
            change = True
            mode = (mode + 1) % 4
        last_time = now

    if (change):
        set_all(0)
        if (mode == 0):
            config = blue_init()
        elif (mode == 1):
            config = starburst_init()
        elif (mode == 2):
            config = sparks_init()
        elif (mode == 3):
            config = white_init()

    return change

# ================
# Main entry point
# ================

# Customer color choice
hue_max = 0.73
hue_min = 0.42
# Mode control
mode = -1
timeout = 2.5
touch_timeout = 0.25

# State
last_time = time.monotonic()
locked = False
while (True):
    # Handle mode switches
    mode_switch()

    # Dynamic modes
    if (mode == 0):
        blue(config)
    elif (mode == 1):
        starburst(config)
    elif (mode == 2):
        sparks(config)
    #elif (mode == 3):
    #    white()