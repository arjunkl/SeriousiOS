#include "SeriousIOSInputBridge.h"

#include <cassert>
#include <cmath>

namespace {

bool approximately(float left, float right) {
    return std::fabs(left - right) < 0.0001f;
}

} // namespace

int main() {
    seriousios::InputBridge bridge;

    bridge.setMovement(1.5f, -1.5f);
    seriousios::InputSnapshot state = bridge.snapshot();
    assert(approximately(state.moveForward, 1.0f));
    assert(approximately(state.moveRight, -1.0f));

    bridge.addLookDelta(3.0f, -2.0f);
    bridge.setAction(2, true);
    state = bridge.consume();
    assert(approximately(state.lookYawDelta, 3.0f));
    assert(approximately(state.lookPitchDelta, -2.0f));
    assert(state.heldActions[2]);
    assert(state.pressedActions[2]);

    state = bridge.snapshot();
    assert(approximately(state.moveForward, 1.0f));
    assert(approximately(state.moveRight, -1.0f));
    assert(approximately(state.lookYawDelta, 0.0f));
    assert(approximately(state.lookPitchDelta, 0.0f));
    assert(state.heldActions[2]);
    assert(!state.pressedActions[2]);

    bridge.setAction(2, false);
    bridge.releaseAll();
    state = bridge.snapshot();
    assert(approximately(state.moveForward, 0.0f));
    assert(approximately(state.moveRight, 0.0f));
    assert(!state.heldActions[2]);
    return 0;
}
