#include "sensor.h"

int sensor_decode(unsigned int raw)
{
    return raw == 0x0fffU ? -1 : 1;
}
