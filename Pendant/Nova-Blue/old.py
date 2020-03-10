import time, math, random
import board, touchio, analogio, digitalio
import neopixel
import adafruit_fancyled.adafruit_fancyled as fancy

# This is the red LED next to the power switch
led_pin = board.D13
led = digitalio.DigitalInOut(led_pin)
led.direction = digitalio.Direction.OUTPUT

# DotStart is the single RGB light on the back of the board, by the reset button
# On the Gemma M0 it's connected to the the SPI interface
try:
    import adafruit_dotstar
    dotstar_len = 1
    dotstar_sck = board.APA102_SCK
    dotstar_mosi = board.APA102_MOSI
    dotstar = adafruit_dotstar.DotStar(dotstar_sck, dotstar_mosi, dotstar_len, brightness=1.0, auto_write=True)
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
neopixel_pin = board.D0
neopixel = neopixel.NeoPixel(neopixel_pin, neopixel_len, brightness=1.0, auto_write=False)
# Noepixels don't light if scaled below this value
neopixel_min = 0.0045

# Analog light sensor GA1A12S202
sensor_pin = board.A1
sensor = analogio.AnalogIn(sensor_pin)
# The raw analog sample scale is 2^16, but the sensor can't quite use that whole range
# GA1A12S202 can output about 2k to 60k, logarithmic (which is useful, since eyes are also log-ish)
sensor_min = 2000
sensor_max = 60000
sensor_range = sensor_max - sensor_min

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
        scale = (sensor.value - sensor_min) / sensor_range
        # Use an exponent to make the scale more sensitive at the low ends
        # Because this value is normalized squaring always makes it smaller (unless you're at 100%)
        scale = scale ** 2
        # Enforce a minimum to avoid blackouts at low ambient light levels
        scale = neopixel_limits(scale)
    return scale

def decay(value, step, rate):
    v = value * (rate ** step)
    v = neopixel_limits(v)
    return v

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
    target = int(start / ring_len) * ring_len
    return target

def set_all(color):
    for j in range(0, neopixel_len):
        neopixel[j] = color
    neopixel.show()

def starburst_init():
    dotstar[0] = (0, 1, 1)
    c = {}
    # 0.0-1.0, bigger numbers decay slower
    c['fade_rate'] = 0.96
    c['ramp_rate'] = 0.80
    # Total steps in the fade/ramp
    c['ramp_steps'] = 10
    c['fade_steps'] = 90
    c['side_delay'] = int(c['ramp_steps'] * 0.75)
    # Flag for mode switch
    c['bright'] = False
    # Math to make the code easier
    c['ramp_index'] = c['ramp_steps'] + 1
    c['side_index'] = c['ramp_steps'] + c['side_delay']
    c['total_steps'] = c['ramp_steps'] + c['fade_steps']
    c['last_step'] = c['total_steps'] - 1
    return c

def starburst(c):
    # Pick a ring pixel other than center
    pixel = None
    while (pixel == None or pixel % ring_len == 0):
        pixel = random.randint(0, neopixel_len - 1)

    # Pick a related set of colors, always full brightness
    hue = random.uniform(hue_min, hue_max)
    color = fancy.CHSV(hue, 1.0, 1.0)
    color_l = fancy.CHSV(hue - 0.08, 0.85, color.value)
    color_r = fancy.CHSV(hue + 0.08, 0.85, color.value)
    color_c = fancy.CHSV(hue, 0.85, color.value)

    for i in range(0, c['total_steps']):
        #  Allow mode switches
        if (mode_switch()):
            return

        # Primary pixel
        if (i <= c['ramp_index']):
            v = decay(color.value, (c['ramp_steps'] - i), c['ramp_rate'])
            f = fancy.CHSV(color.hue, color.saturation, v)
            neopixel[pixel] = f.pack()
        elif (i == c['last_step']):
            neopixel[pixel] = 0
        else:
            v = decay(color.value, i - c['ramp_steps'], c['fade_rate'])
            f = fancy.CHSV(color.hue, color.saturation, v)
            neopixel[pixel] = f.pack()

        # All pixels are primary if the button is pushed (and the mode is locked)
        if (touch.value and locked):
            c['bright'] = True
            for j in range(0, neopixel_len):
                neopixel[j] = neopixel[pixel]
        elif (c['bright']):
            c['bright'] = False
            for j in range(0, neopixel_len):
                if (j != pixel):
                    neopixel[j] = 0
        # Side pixels
        elif (i >= c['side_delay'] and i < c['side_index']):
            s = c['ramp_steps'] + c['side_delay'] - i
            v = decay(color.value * 0.25, s, c['ramp_rate'] * 0.975)
            c_l = fancy.CHSV(color_l.hue, color_l.saturation, v)
            c_r = fancy.CHSV(color_r.hue, color_r.saturation, v)
            c_c = fancy.CHSV(color_c.hue, color_c.saturation, v)
            neopixel[ ring_move(pixel, -1) ] = c_l.pack()
            neopixel[ ring_move(pixel, 1) ] = c_r.pack()
            neopixel[ ring_center(pixel) ] = c_c.pack()
        elif (i < c['side_delay'] or i == c['last_step']):
            neopixel[ ring_move(pixel, -1) ] = 0
            neopixel[ ring_move(pixel, 1) ] = 0
            neopixel[ ring_center(pixel) ] = 0
        else:
            s = i - c['side_delay']
            v = decay(color.value * 0.25, s, c['fade_rate'] * 0.975)
            c_l = fancy.CHSV(color_l.hue, color_l.saturation, v)
            c_r = fancy.CHSV(color_r.hue, color_r.saturation, v)
            c_c = fancy.CHSV(color_c.hue, color_c.saturation, v)
            neopixel[ ring_move(pixel, -1) ] = c_l.pack()
            neopixel[ ring_move(pixel, 1) ] = c_r.pack()
            neopixel[ ring_center(pixel) ] = c_c.pack()

        # Push to hardware
        neopixel.show()
        time.sleep(random.uniform(0.01125, 0.0225))
    time.sleep(random.uniform(0.5, 1.0))

def nextBlue(c):
    hue = random.uniform(hue_min, hue_max)
    value = random.random()
    chaos = random.random()
    if (chaos >= 0.4):
        value /= 12.0;
    value = neopixel_limits(value * scale())
    color = fancy.CHSV(hue, 1.0, value)
    return color

def blue_init():
    dotstar[0] = (0, 0, 1)
    c = {}
    c['current'] = {}
    c['next'] = {}
    for j in range(0, neopixel_len):
        c['current'][j] = 0
        c['next'][j] = 0
    c['timer'] = 0
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

def white():
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
            mode = (mode + 1) % 3
        last_time = now

    if (change):
        set_all(0)
        if (mode == 0):
            config = blue_init()
        elif (mode == 1):
            config = starburst_init()
        elif (mode == 2):
            config = white()

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
#dotstar[0] = 0
while (True):
    # Handle mode switches
    mode_switch()

    # Dynamic modes
    if (mode == 0):
        blue(config)
    elif (mode == 1):
        starburst(config)