#include "HID-Project.h"

// Optional debug build
//#define DEBUG

// Hardware config
const int PROGMEM NUM_POTS = 6; // Number of analog outputs
const int PROGMEM NUM_AXIS_8BIT = 2; // The last two analog outputs are only 8-bit resolution
const int PROGMEM NUM_SWITCHES = 10; // Number of boolean outputs
const int PROGMEM POTS_0 = 1; // Pots start at A1
const int PROGMEM SWITCHES_0 = 3; // Switches start at D3

// Analog sample tuning
const int PROGMEM ANALOG_RES = 16;
int ANALOG_MIN = (2 << (ANALOG_RES / 2));
int ANALOG_MAX = (2 << (ANALOG_RES - 1));
// Undef to use in-band sampling, or define a pin to sample a dedicated reference
#undef ANALOG_MIN_REF
#define ANALOG_MAX_REF A0
// These should be big enough to squelch most sample noise
const int PROGMEM ANALOG_MIN_DEAD = 2 << 7;
const int PROGMEM ANALOG_MAX_DEAD = 2 << 7;

// Runtime data
int pots[NUM_POTS];
int16_t axis[NUM_POTS];
bool switches[NUM_SWITCHES];
String msg = String();

void setup() {
  #ifdef DEBUG
    Serial.begin(9600);
  #endif
  
  // Set all the digital pins we need to INPUT_PULL mode
  // These will float at 1 and change to 0 if shorted to ground
  for (int i = 0; i < NUM_SWITCHES; i++) {
    pinMode(i + SWITCHES_0, INPUT_PULLUP);
  }

  // Set the analog read resolution to 16-bits
  // Older arduinos have 10-bit ADCs, newer have 12-bit ADC
  // This will use to whatever the hardware supports and pad extra bits as needed
  analogReadResolution(ANALOG_RES);

  // Send a clean report to the host
  Gamepad.begin();
}

// Grab the min/max value for analog inputs, if we have a reference pin for either
// Otherwise assume the lowest/highest readings we've seen thus far represent the range
void updateAnalogRange() {
  #ifdef ANALOG_MIN_REF
    ANALOG_MIN = analogRead(ANALOG_MIN_REF);
  #else
    for (uint8_t i = 0; i < NUM_POTS; i++) {
      ANALOG_MIN = min(ANALOG_MIN, pots[i]);
    }
  #endif
  #ifdef ANALOG_MAX_REF
    ANALOG_MAX = analogRead(ANALOG_MAX_REF);
  #else
    for (uint8_t i = 0; i < NUM_POTS; i++) {
      ANALOG_MAX = max(ANALOG_MAX, pots[i]);
    }
  #endif
}

void loop() {  
  // Grab all the inputs
  for (uint8_t i = 0; i < NUM_POTS; i++) {
    pots[i] = analogRead(i + POTS_0);
  }
  for (uint8_t i = 0; i < NUM_SWITCHES; i++) {
    switches[i] = digitalRead(i + SWITCHES_0);
  }

  // Collect analog range data
  updateAnalogRange();

  // Input debug
  #ifdef DEBUG
    msg = "A: ";
    for (uint8_t i = 0; i < NUM_POTS; i++) {
      msg = msg + i + "=" + (String)pots[i] + "\t";
    }
    msg = msg + "Min=" + (String)ANALOG_MIN + "\tMax=" + (String)ANALOG_MAX +
      "\nD: ";
    for (uint8_t i = 0; i < NUM_SWITCHES; i++) {
      msg = msg + i + "=" + (String)switches[i] + "\t";
    }
    Serial.println(msg);
  #endif

  // Invert the digital inputs, since we've instructed them to float high with INPUT_PULLUP
  for (uint8_t i = 0; i < NUM_SWITCHES; i++) {
    switches[i] = !switches[i];
  }

  // Apply deadbands at the edges of the analog signals
  for (uint8_t i = 0; i < NUM_POTS; i++) {
    if (pots[i] < (ANALOG_MIN + ANALOG_MIN_DEAD)) {
      pots[i] = ANALOG_MIN;
    }
    if (pots[i] > (ANALOG_MAX - ANALOG_MAX_DEAD)) {
      pots[i] = ANALOG_MAX;
    }
  }

  // Scale and offset pots into their output axis representations
  for (uint8_t i = 0; i < NUM_POTS; i++) {
    // TODO: Filtering
    if (i < NUM_POTS - NUM_AXIS_8BIT) {
      // 16-bit signed
      float scale = (uint16_t)0xFFFF / (float)(ANALOG_MAX - ANALOG_MIN);
      axis[i] = (int16_t)(scale * (pots[i] - ANALOG_MIN)) - 0x8000;
    } else {
      // 8-bit signed
      float scale = (uint8_t)0xFF / (float)(ANALOG_MAX - ANALOG_MIN);
      axis[i] = (int8_t)(scale * (pots[i] - ANALOG_MIN)) - 0x80;
    }
  }

  // Copy inputs to outputs
  for (int i = 0; i < NUM_SWITCHES; i++) {
    // Output buttons start at 1, so set button number i+1
    if (switches[i]) {
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

  // Output debug
  #ifdef DEBUG
    msg = "Buttons: ";
    for (uint8_t i = 0; i < NUM_SWITCHES; i++) {
      if (switches[i]) {
        msg = msg + i + " ";
      }
    }
    msg = msg + "\nAxes: ";
    for (uint8_t i = 0; i < NUM_POTS; i++) {
      msg = msg + i + "=" + axis[i] + "\t";
    }
    msg = msg + "\n";
    Serial.println(msg);
  #endif

  // Send the gamepad state
  Gamepad.write();
  // Tiny delay to rate-limit updates
  delay(5);

  // Extra delay when in debug mode
  #ifdef DEBUG
    delay(250);
  #endif
}
