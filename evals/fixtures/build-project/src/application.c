#include "sensor.h"

int sample_is_negative(unsigned int raw)
{
    return sensor_decode(raw) < 0;
}
