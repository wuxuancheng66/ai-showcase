import Foundation

@main
struct NativeQueryClassifierMain {
    static func main() {
        let failures = NativeQueryClassifierTests.run()
        print("NATIVE CLASSIFIER RESULT failures=\(failures)")
        exit(failures == 0 ? 0 : 1)
    }
}
