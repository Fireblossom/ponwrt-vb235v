# SPDX-License-Identifier: GPL-2.0-only
CC ?= cc
CFLAGS ?= -O2 -g
WARN = -std=c11 -Wall -Wextra -Werror -Wformat=2 -Wshadow -Wconversion
BUILD ?= build
ifneq ($(words $(BUILD)),1)
$(error BUILD must be a path without spaces)
endif
SOURCES = core.c sha256.c
.PHONY: all test clean
all: $(BUILD)/ponwrt-dsl
$(BUILD):
	mkdir -p "$@"
$(BUILD)/ponwrt-dsl: $(SOURCES) provider.c runtime.c core.h provider.h provider_uapi.h | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(WARN) $(SOURCES) provider.c runtime.c $(LDFLAGS) -o "$@"
$(BUILD)/host-tests: $(SOURCES) host-tests.c core.h | $(BUILD)
	$(CC) $(CPPFLAGS) $(CFLAGS) $(WARN) $(SOURCES) host-tests.c $(LDFLAGS) -o "$@"
test: $(BUILD)/host-tests
	"$(BUILD)/host-tests"
clean:
	rm -f -- "$(BUILD)/ponwrt-dsl" "$(BUILD)/host-tests"
