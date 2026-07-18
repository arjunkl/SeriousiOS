#import <UIKit/UIKit.h>

NS_ASSUME_NONNULL_BEGIN

@interface SeriousIOSTouchOverlayView : UIView <UIGestureRecognizerDelegate>

- (void)updateGameplayActive:(BOOL)gameplayActive
              computerActive:(BOOL)computerActive;
- (void)cancelAllInputWithReason:(NSString*)reason;

@end

NS_ASSUME_NONNULL_END
