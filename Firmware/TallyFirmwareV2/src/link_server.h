#ifndef LINK_SERVER_H
#define LINK_SERVER_H

#include <stdint.h>

#define TALLY_FW_VERSION 1
#define TALLY_TCP_PORT 5198

// Starts the TCP server task on core 0: one client at a time on 192.168.4.1:5198.
void link_server_start(const uint8_t mac[6]);

#endif
