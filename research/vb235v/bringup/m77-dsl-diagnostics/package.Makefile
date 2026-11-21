include $(TOPDIR)/rules.mk

PKG_NAME:=ponwrt-diagnostics
PKG_VERSION:=1
PKG_RELEASE:=1
PKG_LICENSE:=GPL-2.0-only

include $(INCLUDE_DIR)/package.mk

define Package/ponwrt-diagnostics
  SECTION:=utils
  CATEGORY:=Utilities
  TITLE:=PonWrt authenticated device diagnostics
  DEPENDS:=+libjson-c +uci +rpcd +uhttpd +uhttpd-mod-ubus +libustream-openssl +px5g-openssl
endef

define Build/Prepare
	$(INSTALL_DIR) $(PKG_BUILD_DIR)
	$(CP) ./src/*.c $(PKG_BUILD_DIR)/
endef

define Build/Configure
endef

define Build/Compile
	$(TARGET_CC) $(TARGET_CPPFLAGS) $(TARGET_CFLAGS) -std=c11 -Wall -Wextra -Werror $(PKG_BUILD_DIR)/diagnostics.c $(TARGET_LDFLAGS) -ljson-c -o $(PKG_BUILD_DIR)/ponwrt-diag
	$(TARGET_CC) $(TARGET_CPPFLAGS) $(TARGET_CFLAGS) -std=c11 -Wall -Wextra -Werror $(PKG_BUILD_DIR)/setup.c $(TARGET_LDFLAGS) -ljson-c -lcrypt -o $(PKG_BUILD_DIR)/ponwrt-setup
endef

define Package/ponwrt-diagnostics/install
	$(INSTALL_DIR) $(1)/usr/libexec/rpcd $(1)/usr/sbin $(1)/www/cgi-bin
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/ponwrt-diag $(1)/usr/libexec/rpcd/ponwrt.diagnostics
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/ponwrt-setup $(1)/usr/sbin/ponwrt-setup
	$(INSTALL_BIN) $(PKG_BUILD_DIR)/ponwrt-setup $(1)/www/cgi-bin/ponwrt-setup
	$(CP) ./www/. $(1)/www/
	$(INSTALL_DIR) $(1)/etc/init.d $(1)/etc/uci-defaults $(1)/usr/share/rpcd/acl.d
	$(INSTALL_BIN) ./overlay/etc/init.d/ponwrt-diagnostics $(1)/etc/init.d/
	$(INSTALL_BIN) ./overlay/etc/uci-defaults/99-ponwrt-diagnostics $(1)/etc/uci-defaults/
	$(INSTALL_DATA) ./overlay/usr/share/rpcd/acl.d/ponwrt-diagnostics.json $(1)/usr/share/rpcd/acl.d/
endef

$(eval $(call BuildPackage,ponwrt-diagnostics))
