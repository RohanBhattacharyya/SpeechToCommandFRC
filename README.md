# Speech to Command FRC
Software:

<img width="1920" height="930" alt="image" src="https://github.com/user-attachments/assets/fa9d940e-7f2c-4218-9b89-ea289c4329a1" />
Advantage Scope:

<img width="1920" height="1020" alt="image" src="https://github.com/user-attachments/assets/321f4a24-872a-487b-9932-e7a5fd7d8183" />

A laptop-side command listener for FRC robots. It runs a local browser GUI, listens to the laptop microphone with offline Vosk speech recognition, and publishes recognized commands to the robot over NetworkTables using RobotPy's `pyntcore` package.

## What It Publishes

By default the app publishes to the `SpeechToCommand` table:

- `command`: the most recent command name
- `sequence`: an incrementing number so robot code can detect repeated commands
- `heardAt`: local UNIX timestamp
- `connected`: whether the laptop app is currently running

For example, if the table is `SpeechToCommand`, robot code can read `/SpeechToCommand/command` and `/SpeechToCommand/sequence`.

## Install

Python 3.11 or newer is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

Install a Vosk English model from https://alphacephei.com/vosk/models and unzip it somewhere on the laptop. A small model such as `vosk-model-small-en-us-0.15` is enough for command phrases.

## Run

```bash
python3 -m speech_to_command_frc
```

or:

```bash
speech-to-command-frc
```

Then open:

```text
http://127.0.0.1:8765
```

The GUI lets you:

- add and remove persistent command names
- set the robot team number or a specific NetworkTables server address
- set the NetworkTables table name
- set the local Vosk model directory
- start/stop microphone listening
- test recognition by typing sample transcript text

Settings are saved in:

```text
~/.speech_to_command_frc/config.json
```

## Matching Behavior

Commands are matched as whole normalized word sequences. If both `move` and `move diagonally` exist, saying `move diagonally` triggers only `move diagonally`, because overlapping matches choose the longest command.

## Robot-Side Sketch

Java example:

```java
NetworkTable table = NetworkTableInstance.getDefault().getTable("SpeechToCommand");
String lastCommand = "";
double lastSequence = -1;

public void teleopPeriodic() {
  String command = table.getEntry("command").getString("");
  double sequence = table.getEntry("sequence").getDouble(-1);

  if (sequence != lastSequence) {
    lastSequence = sequence;
    lastCommand = command;

    if (command.equals("move diagonally")) {
      // Run that command
    }
  }
}
```
