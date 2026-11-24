# iPhone Server

这是旧版 Swift 手机自动化原型的技术案例。设备控制使用 WebDriverAgent 和 XCTest。已知结构包括本机只读查询、深链入口、操作结果观察与中断记录。[阅读案例](https://wuxuancheng66.github.io/ai-showcase/20-iphone-server/)

这里提供应用中使用的只读模块 `NativeDeviceQuery.swift`、现有回归断言和命令行测试入口。模块能识别明确的系统版本、电量、充电状态和低电量模式查询。碰到混合或歧义指令时让调用者进一步处理。iOS 端的读取使用 UIKit 与 Foundation，无需屏幕操作或模型调用。

macOS 上用 Swift 运行分类回归：

```sh
swiftc NativeDeviceQuery.swift NativeQueryClassifierTests.swift NativeQueryClassifierMain.swift -o /tmp/iphone-query-tests
/tmp/iphone-query-tests
```

UIKit 读取分支需要 iOS。CoreDevice 迁移与 MCP 接口尚未验证。此目录只分发上面的独立模块，不包含可安装 App 或设备连接配置。
