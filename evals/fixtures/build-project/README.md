# Linux sensor sample

This project reproduces an embedded application's build and test layout on the
development host. The selected product is `host-linux-sample`; GCC produces native
Linux executables and shared libraries. No cross toolchain, board, SSH server or
hardware peripheral is needed or configured.

`src/sensor.c` decodes a signed 12-bit two's-complement sample. Values `0x000` through
`0x7ff` represent 0 through 2047; `0x800` through `0xfff` represent -2048 through -1.
Bits above bit 11 are ignored. `src/application.c` consumes this conversion.
The current source contains the negative-value fix; preserve it.

Use the existing entrypoints from this directory:

| Command | Operation |
| --- | --- |
| `python3 project.py build` | Compile `src/` to `build/`; does not stage or package |
| `python3 project.py stage` | Copy the existing build to `stage/bin/` and `stage/lib/` |
| `python3 project.py package` | Create `output/application.tar` using `package.json` and `stage/bin/sample`; does not compile or stage |
| `python3 project.py test` | Compile and execute the cases registered in `tests/suite.json` |

`package.json` owns the product and package library input. `vendor/` holds a supplied
prebuilt library. `build/`, `stage/` and `output/` are generated files.

`tests/suite.json` maps a case name to the C source files linked into its executable.
Each case supplies its own `main`, returns zero on success and nonzero on failure;
assertions are enabled. Sources live under `src/` or `tests/`, and headers are found
under `src/`. New regression cases belong in this existing runner. The initial
application test uses `tests/sensor_stub.c` in place of the sensor conversion.

Save evidence under `evidence/`. Do not access real devices or external services.
