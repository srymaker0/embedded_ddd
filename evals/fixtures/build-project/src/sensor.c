#include "sensor.h"

/* The sample field is a signed, 12-bit two's-complement value. */
int sensor_decode(unsigned int raw)
{
    int value = (int)(raw & 0x0fffU);
    return (value & 0x0800) ? value - 4096 : value;
}
