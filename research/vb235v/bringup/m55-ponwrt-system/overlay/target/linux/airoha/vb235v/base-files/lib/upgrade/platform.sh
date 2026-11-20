# SPDX-License-Identifier: GPL-2.0-only
REQUIRE_IMAGE_METADATA=1

platform_check_image() {
	echo 'VB235v RAM development: persistent system installation is not validated.' >&2
	return 1
}

platform_do_upgrade() {
	echo 'VB235v RAM development: no persistent upgrade backend.' >&2
	return 1
}
