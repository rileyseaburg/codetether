// swift-tools-version: 5.9
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "A2AMonitor",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        .executable(
            name: "A2AMonitor",
            targets: ["A2AMonitor"]),
    ],
    targets: [
        .executableTarget(
            name: "A2AMonitor",
            dependencies: [],
            path: "Sources/A2AMonitor"
        ),
    ]
)
