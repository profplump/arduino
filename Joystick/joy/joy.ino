#include "HID-Project.h"

// Plus 1, so we can get an analog max voltage and a digital mode switch
const int PROGMEM NUM_POTS = 6 + 1;
const int PROGMEM NUM_SWITCHES = 8 + 1;
const int PROGMEM MODE = 2; // Digital 0-1 are used for RX/TX
const int PROGMEM REF = A0;
const int PROGMEM ANALOG_MIN = 10; // Low-end deadband, since 0 floats a bit

int pots[NUM_POTS];
uint16_t axis[NUM_POTS - 1];
bool switches[NUM_SWITCHES];

void setup() {
  // Debug console
  Serial.begin(9600);
  Serial.println("Started");
  
  // Set all the digital pins we need to INPUT_PULL mode
  // These will float at 1 and change to 0 if shorted to ground
  for (int i = 0; i < NUM_SWITCHES; i++) {
    pinMode(i + MODE, INPUT_PULLUP);
  }

  // Sends a clean report to the host. This is important on any Arduino type.
  Gamepad.begin();
  pinMode(12, INPUT);
}

void loop() {
  // Testing mode, when pin12 is high
  if (digitalRead(12)) {
  // Sends the full range of each analog axis
  Serial.println("Full");
  Gamepad.xAxis(0xFFFF);
  Gamepad.yAxis(0xFFFF);
  Gamepad.zAxis(0xFFFF);
  Gamepad.rxAxis(0xFFFF);
  Gamepad.ryAxis(0xFFFF);
  Gamepad.rzAxis(0xFFFF);
  Gamepad.write();
  delay(500);
  Serial.println("Half");
  Gamepad.xAxis(0x00FF);
  Gamepad.yAxis(0x00FF);
  Gamepad.zAxis(0x00FF);
  Gamepad.rxAxis(0x00FF);
  Gamepad.ryAxis(0x00FF);
  Gamepad.rzAxis(0x00FF);
  Gamepad.write();
  delay(500);
  Serial.println("Zero");
  Gamepad.xAxis(0x0000);
  Gamepad.yAxis(0x0000);
  Gamepad.zAxis(0x0000);
  Gamepad.rxAxis(0x0000);
  Gamepad.ryAxis(0x0000);
  Gamepad.rzAxis(0x0000);
  Gamepad.write();
  delay(500);
  Serial.println("Random");
  int foo = random(0xFFFF);
  Serial.println(foo);
  Gamepad.rzAxis(foo);
  Gamepad.write();
  delay(1000);
  return;
  }
  
  // If we're not in test mode
  if (digitalRead(MODE)) {

    // Grab all the inputs
    for (uint8_t i = 0; i < NUM_POTS; i++) {
      pots[i] = analogRead(i + REF);
      if (pots[i] < ANALOG_MIN) {
        pots[i] = 0;
      }
    }
    for (uint8_t i = 0; i < NUM_SWITCHES; i++) {
      switches[i] = digitalRead(i + MODE);
    }

    // Scale analog inputs to the reference input
    // Skip the REF pot, as we use that for scaling
    Serial.print("Ref: ");
    Serial.println(pots[0]);
    float scale = (uint16_t)0xFFFF / (float)pots[0];
    Serial.print("Scale: ");
    Serial.println(scale);
    for (uint8_t i = 1; i < NUM_POTS; i++) {
      // TODO: Filtering      
      axis[i - 1] = (uint16_t)(scale * pots[i]);
      Serial.print("a0[");
      Serial.print(i - 1);
      Serial.print("]: ");
      Serial.print(axis[i - 1]);
      Serial.print(" ");
      Serial.println((float)axis[i - 1] / (uint16_t)0xFFFF);
    }
    Serial.println();

    
    // Copy inputs to outputs
    for (int i = 1; i < NUM_SWITCHES; i++) {
      // LOW is pressed because we init to INPUT_PULLUP
      // Buttons start at 1, so i=1 works for everything
      if (switches[i] == LOW) {
        Gamepad.press(i);
      } else {
        Gamepad.release(i);
      }
    }
    Gamepad.xAxis(axis[0]);
    Gamepad.yAxis(axis[1]);
    Gamepad.zAxis(axis[2]);
    Gamepad.rxAxis(axis[3]);
    Gamepad.ryAxis(axis[4]);
    Gamepad.rzAxis(axis[5]);

  // If we are in test mode
  } else {

    // Press button 1-32
    static uint8_t count = 0;
    count++;
    if (count == 33) {
      Gamepad.releaseAll();
      count = 0;
    } else {
      Gamepad.press(count);
    }

    // Move x/y Axis to a random 16-bit location
    Gamepad.xAxis(random(0xFFFF));
    Gamepad.yAxis(random(0xFFFF));
    Gamepad.zAxis(random(0xFFFF));
    Gamepad.rxAxis(random(0xFFFF));
    Gamepad.ryAxis(random(0xFFFF));
    Gamepad.rzAxis(random(0xFFFF));

    // Go through all dPad positions
    // values: 0-8 (0==centered)
    static uint8_t dpad1 = GAMEPAD_DPAD_CENTERED;
    Gamepad.dPad1(dpad1++);
    if (dpad1 > GAMEPAD_DPAD_UP_LEFT) {
      dpad1 = GAMEPAD_DPAD_CENTERED;
    }
    static int8_t dpad2 = GAMEPAD_DPAD_CENTERED;
    Gamepad.dPad2(dpad2--);
    if (dpad2 < GAMEPAD_DPAD_CENTERED) {
      dpad2 = GAMEPAD_DPAD_UP_LEFT;
    }
  }

  // In all modes

  // Send the gamepad state
  Gamepad.write();
  // Debounce via delay
  delay(500);
}
