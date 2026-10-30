#ifndef SENSOR_H
#define SENSOR_H

int sensor_decode(unsigned int raw);
int sample_is_negative(unsigned int raw);

#endif
