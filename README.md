# 中弘VRF网关 (绿米版) Home Assistant集成

集成使用了HTTP+TCP混合的方式解决了原有HTTP方式响应延迟的问题，使用体验更友好。

> [!WARNING]
> 
> 该集成仅适用于中弘VRF绿米版本的网关，经过重置，现在支持多个外机（仅测试到2个）

# 安装方式

## 使用 HACS 安装

[![打开 Home Assistant 并打开 HACS商店内的存储库。](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Johnnybyzhang&repository=Zhong_Hong_VRF&category=integration)

## 手动安装

将 `custom_components` 下的 `zhong_hong_vrf` 文件夹到 Home Assistant 中的`custom_components` 目录，并手动重启 Home Assistant。

# 设置

[![打开 Home Assistant 并设置新的集成。](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=zhong_hong_vrf)

> [!CAUTION]
> 
> 如果您无法使用上面的按钮，请按照以下步骤操作：
> 
> 1. 导航到 Home Assistant 集成页面（设置 --> 设备和服务）
> 2. 单击右下角的 `+ 添加集成` 按钮
> 3. 搜索 `Zhong Hong VRF`

> [!NOTE]
> 
> 1. 网关IP请填写VRF的IP地址
> 2. TCP端口默认为`9999`
> 3. 用户名默认为`admin`
> 4. 密码默认为空
> 5. 从UI控制设备后会立即主动拉取一次最新状态

# Credits
[xswxm/home-assistant-zhong-hong](https://github.com/xswxm/home-assistant-zhong-hong)
