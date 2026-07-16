// Runtime globals normally owned by the desktop SeriousSam executable.
// The native iOS app host will own and update these values during startup.

class CGame;

CGame* _pGame = nullptr;
void* _hwndMain = nullptr;
