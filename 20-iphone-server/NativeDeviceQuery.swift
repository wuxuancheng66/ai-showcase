import Foundation

#if canImport(UIKit)
import UIKit
#endif

/// 严格、只读、完全本机的快捷路径；任何未解释的要求都交回通用执行器。
enum NativeDeviceQuery {
    enum Field: CaseIterable, Hashable {
        case systemVersion, battery, charging, lowPower
    }
    struct Query: Equatable { let fields: Set<Field> }
    struct Result {
        let text: String
        let complete: Bool
    }

    static func parse(_ request: String) -> Query? {
        guard request.count <= 200 else { return nil }
        var rest = request.lowercased().filter { !$0.isWhitespace }
        var fields = Set<Field>()
        // 先消耗“低电量模式”，不能将其中的“电量”误建为另一项任务。
        let groups: [(Field, [String])] = [
            (.lowPower, ["低电量模式是否开启", "是否开启低电量模式", "低电量模式开没开", "低电量模式状态", "低电量模式"]),
            (.systemVersion, ["ios系统版本", "手机系统版本", "ios版本", "系统版本"]),
            (.charging, ["是否正在充电", "有没有在充电", "是否在充电", "是否充电", "正在充电吗", "充电状态"]),
            (.battery, ["电池的电量", "电池剩余电量", "剩余电量", "电池电量", "电量百分比", "电池百分比", "电量"]),
        ]
        for (field, phrases) in groups {
            for phrase in phrases.sorted(by: { $0.count > $1.count }) where rest.contains(phrase) {
                fields.insert(field)
                rest = rest.replacingOccurrences(of: phrase, with: "")
            }
        }
        guard !fields.isEmpty else { return nil }
        // “电池/状态”可代表额外目标，“显示”也可能要求改显示开关，不能当作通用填充词。
        let glue = ["告诉我", "帮我", "请问", "查看一下", "查看", "查询", "查一下", "读取", "获取",
                    "看一下", "看下", "看看", "当前", "现在", "目前", "这台", "这部", "我的", "手机", "iphone",
                    "设备", "分别", "是多少", "是什么", "多少", "以及", "还有", "谢谢", "一下",
                    "请", "的", "和", "及", "与", "吗", "呢"]
        for phrase in glue.sorted(by: { $0.count > $1.count }) {
            rest = rest.replacingOccurrences(of: phrase, with: "")
        }
        let punctuation = CharacterSet(charactersIn: "，,。.!！?？、;；:：")
        rest = rest.unicodeScalars.filter { !punctuation.contains($0) }.map(String.init).joined()
        guard rest.isEmpty else { return nil }
        return Query(fields: fields)
    }

    #if canImport(UIKit)
    /// 不读取名字、设备标识或用户数据；不打开 App，不截图，不访问网络。
    @MainActor
    static func read(_ query: Query) -> Result {
        let device = UIDevice.current
        let needsBattery = !query.fields.isDisjoint(with: [.battery, .charging])
        let wasMonitoring = device.isBatteryMonitoringEnabled
        if needsBattery && !wasMonitoring { device.isBatteryMonitoringEnabled = true }
        defer { if needsBattery && !wasMonitoring { device.isBatteryMonitoringEnabled = false } }

        var lines: [String] = []
        var complete = true
        for field in Field.allCases where query.fields.contains(field) {
            switch field {
            case .systemVersion:
                let version = device.systemVersion
                if version.range(of: #"^\d+(?:\.\d+){1,3}$"#, options: .regularExpression) != nil {
                    lines.append("系统版本：iOS " + version)
                } else { lines.append("系统版本：暂时无法读取"); complete = false }
            case .battery:
                let level = device.batteryLevel
                if level.isFinite && (0...1).contains(level) {
                    lines.append("电量：\(Int((level * 100).rounded()))%")
                } else { lines.append("电量：暂时无法读取"); complete = false }
            case .charging:
                switch device.batteryState {
                case .unplugged: lines.append("充电状态：未连接充电器")
                case .charging: lines.append("充电状态：正在充电")
                case .full: lines.append("充电状态：已充满")
                case .unknown: lines.append("充电状态：暂时无法读取"); complete = false
                @unknown default: lines.append("充电状态：暂时无法读取"); complete = false
                }
            case .lowPower:
                lines.append("低电量模式：" + (ProcessInfo.processInfo.isLowPowerModeEnabled ? "已开启" : "未开启"))
            }
        }
        lines.append("来源：本机系统接口，未进行屏幕操作。")
        return Result(text: lines.joined(separator: "\n"), complete: complete)
    }
    #endif
}
