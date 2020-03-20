#include "HID-Project.h"

const int PROGMEM NUM_POTS = 6;
const int PROGMEM NUM_SWITCHES = 4;
const int PROGMEM POTS_0 = 1; // Pots start at Analog1
const int PROGMEM NUM_AXIS_8BIT = 2; // The last two analog inputs are only 8-bit resolution
const int PROGMEM SWITCHES_0 = 3; // Switches start at Digital3
const int PROGMEM ANALOG_MIN_DEAD = 12; // Low-end deadband, since the pots don't quite go to 0
const int PROGMEM ANALOG_MAX_DEAD = 12; // High-end deadband, since the pots don't quite go to ANALOG_MAX

// Do we have analog reference pins?
#define ANALOG_MAX_REF A0
#undef ANALOG_MIN_REF

int ANALOG_MAX = 1024;
int pots[NUM_POTS];
int16_t axis[NUM_POTS];
bool switches[NUM_SWITCHES];

void setup() {
  // Debug console
  Serial.begin(9600);
  Serial.println("Started");
  
  // Set all the digital pins we need to INPUT_PULL mode
  // These will float at 1 and change to 0 if shorted to ground
  for (int i = 0; i < NUM_SWITCHES; i++) {
    pinMode(i + SWITCHES_0, INPUT_PULLUP);
  }

  // Sends a clean report to the host. This is important on any Arduino type.
  Gamepad.begin();
}

// Grab the maximum value for analog inputs
void updateAnalogRange() {
  #ifdef ANALOG_MAX_REF
    int ref = analogRead(ANALOG_MAX_REF);
    if (ref > ANALOG_MAX) {
      ANALOG_MAX = ref;
    }
  #endif
  #ifdef ANALOG_MIN_REF
    int ref = analogRead(ANALOG_MIN_REF);
  #endif
}

void loop() {
  updateAnalogRange();
  
  // Grab all the inputs
  for (uint8_t i = 0; i < NUM_POTS; i++) {
    pots[i] = analogRead(i + POTS_0);
  }
  for (uint8_t i = 0; i < NUM_SWITCHES; i++) {
    switches[i] = digitalRead(i + SWITCHES_0);
  }

  // Apply deadbands at the edge of analog signal
  for (uint8_t i = 0; i < NUM_POTS; i++) {
    if (pots[i] < ANALOG_MIN_DEAD) {
      pots[i] = 0;
    }
    if (pots[i] > (ANALOG_MAX - ANALOG_MAX_DEAD)) {
      pots[i] = ANALOG_MAX;
    }
  }

  // Invert the digital inputs, since we've instructed them to float high
  for (uint8_t i = 0; i < NUM_SWITCHES; i++) {
    switches[i] = (switches[i] == LOW) ? HIGH : LOW;
  }

  // Scale and offset pots into their HID axis representations
  for (uint8_t i = 0; i < NUM_POTS; i++) {
    // TODO: Filtering
    if (i < NUM_POTS - NUM_AXIS_8BIT) {
      // 16-bit HID data
      float scale = (uint16_t)0xFFFF / (float)ANALOG_MAX;
      axis[i] = (int16_t)(scale * pots[i]) - 0x8000;
    } else {
      // 8-bit HID data
      float scale = (uint8_t)0xFF / (float)ANALOG_MAX;
      axis[i] = (int16_t)(scale * pots[i]) - 0x80;
    }
  }

  // Copy inputs to outputs
  for (int i = 0; i < NUM_SWITCHES; i++) {
    // HID buttons start at 1, so set button number i+1
    if (switches[i] == HIGH) {
      Gamepad.press(i + 1);
    } else {
      Gamepad.release(i + 1);
    }
  }
  Gamepad.xAxis(axis[0]);
  Gamepad.yAxis(axis[1]);
  Gamepad.rxAxis(axis[2]);
  Gamepad.ryAxis(axis[3]);
  Gamepad.zAxis(axis[4]);
  Gamepad.rzAxis(axis[5]);

  // Send the gamepad state
  Gamepad.write();
  // Tiny delay to rate-limit updates
  delay(5);
}
