import time
import board
import touchio
import analogio
import digitalio
import neopixel
import adafruit_dotstar
import adafruit_fancyled.adafruit_fancyled as fancy

# This is the red LED next to the power switch
led_pin = board.D13
led = digitalio.DigitalInOut(led_pin)
led.direction = digitalio.Direction.OUTPUT

# DotStart is the single RGB light on the back of the board, by the reset button
# On the Gemma M0 it's connected to the the SPI interface
dotstar_len = 1
dotstar_sck = board.APA102_SCK
dotstar_mosi = board.APA102_MOSI
dotstar = adafruit_dotstar.DotStar(dotstar_sck, dotstar_mosi, dotstar_len, brightness=1.0, auto_write=True)

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
neopixel_len = 14 + 8
neopixel_pin = board.D0
neopixel = neopixel.NeoPixel(neopixel_pin, neopixel_len, brightness=1.0, auto_write=False)
# Noepixels don't light if scaled below this value
neopixel_min = 0.004

# Analog light sensor GA1A12S202
sensor_pin = board.A1
sensor = analogio.AnalogIn(sensor_pin)
# The raw analog sample scale is 2^16, but the sensor can't quite use that whole range
# GA1A12S202 can output about 2k to 60k, logarithmic (which is useful, since eyes are also log-ish)
sensor_min = 2000
sensor_max = 60000
sensor_range = sensor_max - sensor_min

FADE = 8
orange = fancy.CHSV(0.08, 1.0, 0.01)
purple = fancy.CHSV(0.75, 1.0, 0.01)

def scale():
    # Normalize (0.0 - 1.0)
    scale = (sensor.value - sensor_min) / sensor_range
    # Use an exponent to make the scale more sensitive at the low ends
    # Because this value is normalized squaring always makes it smaller (unless you're at 100%)
    scale = scale ** 2
    # Enforce a minimum to avoid blackouts at low ambient light levels
    scale = max(scale, neopixel_min)
    return scale

def chase(color):
    scaled = fancy.CHSV(color.hue, color.saturation, color.value * scale())
    for i in range(0, neopixel_len):
        neopixel[i] = color.pack()
        for j in range(0, FADE):
            v = scaled.value / (j + 1)
            c = fancy.CHSV(scaled.hue, scaled.saturation, v)
            neopixel[i - j] = c.pack()
        neopixel[i - FADE] = 0
        neopixel.show()

def setLED(touch):
    if (touch.value):
        led.value = True
    else:
        led.value = False

while True:
    setLED(touch)
    dotstar.fill(purple.pack())
    chase(fancy.CHSV(0/3))

    setLED(touch)
    dotstar.fill(purple.pack())
    chase(fancy.CHSV(1/3))

    setLED(touch)
    dotstar.fill(orange.pack())
    chase(fancy.CHSV(2/3))

    setLED(touch)
    dotstar.fill(0)
    chase(fancy.CHSV(0, 0))