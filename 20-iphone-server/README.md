# iPhone Server

An early Swift prototype for iPhone automation using WebDriverAgent and XCTest. It uses system APIs for simple read-only tasks, deep links for known destinations, and screen observations to verify what happened after an action. [Read the case study](https://wuxuancheng66.github.io/ai-showcase/20-iphone-server/)

This directory contains the app's read-only module, `NativeDeviceQuery.swift`, and its classifier regression tests. It recognizes requests for the iOS version, battery level, charging state, and Low Power Mode. If a request mixes supported and unsupported tasks or is ambiguous, the module leaves it to the caller. The iOS read path uses UIKit and Foundation without screen interaction or a model call.

Run the classifier tests on macOS:

```sh
swiftc NativeDeviceQuery.swift NativeQueryClassifierTests.swift NativeQueryClassifierMain.swift -o /tmp/iphone-query-tests
/tmp/iphone-query-tests
```

The UIKit read path requires iOS. CoreDevice support and an MCP interface are still unverified. The public source covers the standalone read-only module.
