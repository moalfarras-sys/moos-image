// Native reader is mandatory in the image. Kept behind a local component so
// a source preview on an older signed OS can retain its original fallback.
import QtQml
import org.moos.appearance 1.0
QtObject {
    readonly property QtObject value: Appearance
}
