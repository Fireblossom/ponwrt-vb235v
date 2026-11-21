# SPDX-License-Identifier: GPL-2.0-only
include $(TOPDIR)/rules.mk
PKG_NAME:=ponwrt-dsl-runtime
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)
include $(INCLUDE_DIR)/package.mk
define Package/ponwrt-dsl-runtime
  SECTION:=net
  CATEGORY:=Network
  TITLE:=PonWrt fail-closed native DSL bootstrap development runtime
  DEPENDS:=@TARGET_airoha +libgcc
endef
define Package/ponwrt-dsl-runtime/conffiles
/etc/config/ponwrt-dsl
endef
define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
	$(CP) ./src/* $(PKG_BUILD_DIR)/
endef
define Build/Compile
	$(TARGET_CC) $(TARGET_CPPFLAGS) $(TARGET_CFLAGS) -std=c11 -Wall -Wextra -Werror \
		$(PKG_BUILD_DIR)/core.c $(PKG_BUILD_DIR)/sha256.c \
		$(PKG_BUILD_DIR)/provider.c $(PKG_BUILD_DIR)/runtime.c \
		$(TARGET_LDFLAGS) -o $(PKG_BUILD_DIR)/ponwrt-dsl
endef
define Package/ponwrt-dsl-runtime/install
	$(INSTALL_DIR) $(1)/usr/sbin $(1)/etc/init.d $(1)/etc/config
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/ponwrt-dsl $(1)/usr/sbin/
	$(INSTALL_BIN) ./ponwrt-dsl.init $(1)/etc/init.d/ponwrt-dsl
	$(INSTALL_CONF) ./ponwrt-dsl.config $(1)/etc/config/ponwrt-dsl
endef
$(eval $(call BuildPackage,ponwrt-dsl-runtime))
