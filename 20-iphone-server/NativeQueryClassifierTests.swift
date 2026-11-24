import Foundation

enum NativeQueryClassifierTests {
    static func run() -> Int {
        var failures = 0
        func check(_ ok: Bool, _ label: String) {
            print("\(ok ? "PASS" : "FAIL") \(label)")
            if !ok { failures += 1 }
        }
        let unknownStates = ["查询系统版本和电池状态", "查询电量和设备状态", "读取系统版本及手机状态"]
        check(unknownStates.allSatisfy { NativeDeviceQuery.parse($0) == nil },
              "未知的电池或设备状态要求不能被当作语气词删掉，导致只完成已知字段")
        check(NativeDeviceQuery.parse("查询电量和电池") == nil,
              "另行提出的电池要求不明确时，不能借设备修饰词规则静默忽略")
        check(NativeDeviceQuery.parse("显示电量百分比") == nil,
              "可能指设置显示开关的歧义要求不能被直接完成为只读数值")
        check(NativeDeviceQuery.parse("查询电池的电量")?.fields == [.battery] &&
              NativeDeviceQuery.parse("查询电池剩余电量")?.fields == [.battery],
              "收紧分类时仍应支持完整且明确的电池电量短语")
        check(NativeDeviceQuery.parse("请查看手机电量、充电状态和系统版本。")?.fields == [.battery, .charging, .systemVersion],
              "实际界面示例仍须完整走原生只读路径")
        check(NativeDeviceQuery.parse("低电量模式状态和充电状态")?.fields == [.lowPower, .charging],
              "已支持的明确状态字段不能因拒绝未知状态而误退回屏幕操作")
        return failures
    }
}
