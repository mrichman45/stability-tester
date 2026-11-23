import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support

// Game GPU widget: shows and sets the mode in ~/.config/gpu-mode.
// Steam is started through gpu-run, so a mode change applies after Steam restarts.
PlasmoidItem {
    id: root

    property string mode: "auto"
    property bool onAC: false
    property string steamMode: ""       // GPU Steam was started on (from ~/.config/gpu-mode-steam)
    property bool steamRunning: false
    property bool restarting: false

    readonly property string effective: mode === "auto" ? (onAC ? "nvidia" : "intel") : mode
    readonly property bool needsRestart: steamRunning && steamMode !== effective

    readonly property var labels: ({ "auto": "Auto", "intel": "Intel", "nvidia": "NVIDIA" })
    readonly property var details: ({
        "auto": "GTX 1650 when plugged in, Intel on battery",
        "intel": "Always the Intel GPU (saves battery)",
        "nvidia": "Always the GTX 1650"
    })

    // Line 1: mode. Then ac=0/1, steam=<intel|nvidia>, running=1 if Steam is open.
    readonly property string readCmd: "sh -c 'cat \"$HOME/.config/gpu-mode\" 2>/dev/null || echo auto; "
        + "for p in /sys/class/power_supply/*; do "
        + "[ \"$(cat \"$p/type\" 2>/dev/null)\" = Mains ] && echo ac=$(cat \"$p/online\" 2>/dev/null); "
        + "done; "
        + "echo steam=$(cat \"$HOME/.config/gpu-mode-steam\" 2>/dev/null); "
        + "pgrep -x steam >/dev/null && echo running=1; true'"
    readonly property string restartCmd: "sh -c '\"$HOME/.local/bin/steam-restart\"'"

    P5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => {
            if (sourceName === root.readCmd) {
                const lines = (data["stdout"] || "").trim().split("\n").map(l => l.trim());
                const m = lines[0] || "";
                root.mode = (m === "intel" || m === "nvidia") ? m : "auto";
                root.onAC = lines.indexOf("ac=1") >= 0;
                root.steamRunning = lines.indexOf("running=1") >= 0;
                const s = lines.find(l => l.startsWith("steam=")) || "steam=";
                root.steamMode = s.substring(6);
            } else if (sourceName === root.restartCmd) {
                root.restarting = false;
                root.refresh();
            }
            disconnectSource(sourceName);
        }
        function run(cmd) {
            connectSource(cmd);
        }
    }

    function refresh() {
        exec.run(readCmd);
    }

    function setMode(m) {
        root.mode = m;
        exec.run("sh -c 'mkdir -p \"$HOME/.config\" && echo " + m + " > \"$HOME/.config/gpu-mode\"'");
    }

    function cycle() {
        setMode(mode === "auto" ? "intel" : mode === "intel" ? "nvidia" : "auto");
    }

    function restartSteam() {
        root.restarting = true;
        exec.run(restartCmd);
    }

    // Keeps the widget in sync with the Meta+Alt+G shortcut, the charger and Steam
    Timer {
        interval: 2000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.refresh()
    }

    Plasmoid.icon: "video-display"
    Plasmoid.status: needsRestart ? PlasmaCore.Types.NeedsAttentionStatus : PlasmaCore.Types.ActiveStatus
    toolTipMainText: "Game GPU: " + labels[mode] + (mode === "auto" ? " (" + labels[effective] + ")" : "")
    toolTipSubText: (needsRestart
        ? "Steam is still on " + (labels[steamMode] || "the old GPU") + ". Restart Steam to apply."
        : (steamRunning ? "Steam is running on " + labels[steamMode] + "." : "Steam will start on " + labels[effective] + "."))
        + "\nClick to choose · middle-click to cycle"

    preferredRepresentation: compactRepresentation

    compactRepresentation: MouseArea {
        id: compact

        readonly property bool showLabel: Plasmoid.formFactor === PlasmaCore.Types.Horizontal

        Layout.minimumWidth: height + (showLabel ? label.implicitWidth + Kirigami.Units.smallSpacing : 0)
        Layout.preferredWidth: Layout.minimumWidth

        hoverEnabled: true
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        onClicked: mouse => {
            if (mouse.button === Qt.MiddleButton) {
                root.cycle();
            } else {
                root.expanded = !root.expanded;
            }
        }

        Kirigami.Icon {
            id: icon
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: height
            source: "video-display"
            active: compact.containsMouse
        }

        PlasmaComponents3.Label {
            id: label
            visible: compact.showLabel
            anchors.left: icon.right
            anchors.leftMargin: Kirigami.Units.smallSpacing
            anchors.verticalCenter: parent.verticalCenter
            text: (root.mode === "auto" ? "Auto (" + root.labels[root.effective] + ")" : root.labels[root.mode])
                + (root.needsRestart ? " ↻" : "")
        }
    }

    fullRepresentation: ColumnLayout {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 17
        spacing: Kirigami.Units.smallSpacing

        Kirigami.Heading {
            level: 4
            text: "GPU for games"
            Layout.fillWidth: true
        }

        Repeater {
            model: ["auto", "intel", "nvidia"]

            delegate: PlasmaComponents3.RadioButton {
                required property string modelData
                Layout.fillWidth: true
                text: root.labels[modelData] + " – " + root.details[modelData]
                checked: root.mode === modelData
                onToggled: root.setMode(modelData)
            }
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        PlasmaComponents3.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: !root.steamRunning
                ? "Steam isn't running. It will start on " + root.labels[root.effective] + "."
                : root.needsRestart
                    ? "Steam is running on " + (root.labels[root.steamMode] || "the old GPU")
                      + ". Restart it to switch games to " + root.labels[root.effective] + ". Close any game first."
                    : "Steam is running on " + root.labels[root.steamMode] + "."
        }

        PlasmaComponents3.Button {
            visible: root.needsRestart || root.restarting
            enabled: !root.restarting
            Layout.alignment: Qt.AlignRight
            icon.name: "view-refresh"
            text: root.restarting ? "Restarting Steam…" : "Restart Steam on " + root.labels[root.effective]
            onClicked: root.restartSteam()
        }

        PlasmaComponents3.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            opacity: 0.7
            text: "Charger: " + (root.onAC ? "connected" : "not connected")
                + (root.mode === "auto" ? ". Auto is decided when Steam starts." : ".")
        }
    }
}
