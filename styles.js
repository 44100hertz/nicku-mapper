// Port of styles.lua (same colors, same type names) plus a few extra
// palettes for entity types seen in the level files that styles.lua
// didn't cover (they would otherwise fall back to gray).

export const STYLES = {
  default: { col: [0.75, 0.75, 0.75], size: 0.25 },

  ABob: { col: [1.0, 0.9, 0], size: 2 },
  ADanny: { col: [0.5, 0.5, 0.5], size: 2 },
  AJimmy: { col: [1.0, 0.5, 0], size: 2 },
  ATimmy: { col: [1.0, 0.2, 0.8], size: 2 },

  ASandy: { col: [0.5, 0.3, 0], size: 1 },
  ABikiniBottomRebelEntity: { col: [0.2, 0.6, 0.2], size: 1 },

  AFlyingDutchman: { col: [0.0, 1.0, 0.0], size: 2 },

  ARespawnPoint: { col: [1, 0.5, 0], size: 1 },
  ADeathZone: { col: [1, 0, 0] },
  AHardDeathZone: { col: [0.9, 0.1, 0.1] },
  APropPlayerTeleport: { col: [1, 0, 1] },

  AWaypointEntity: { col: [0, 0.5, 0] },
  ATriggerCounter: { col: [0, 0.8, 0.5] },

  APropTrigger: { col: [0, 1, 1] },
  APropTriggerText: { col: [0.5, 0, 1] },
  APropTriggerSS: { col: [0, 0.5, 1] },
  APropTriggerEndLevel: { col: [0, 0, 0] },
  APropTriggerAnimation: { col: [0.4, 0.8, 0.9] },
  APropTriggerReverb: { col: [0.3, 0.5, 0.9] },
  AEnemyTrigger: { col: [0.5, 0.5, 1] },
  APropFlyThroughTrigger: { col: [0.5, 0.75, 1] },
  AParticleEffectTrigger: { col: [0.7, 0.8, 1.0] },
  AMusicTrigger: { col: [0.9, 0.5, 0.9] },
  ATimer: { col: [1.0, 1.0, 0.5] },
  APropTutorial: { col: [0.9, 0.7, 0.3] },

  APropInteractable: { col: [0.5, 0.5, 0] },
  APropDoor: { col: [0, 0.5, 0.5] },
  APropDoorToggle: { col: [0.3, 0.7, 0.9] },
  APropPortal: { col: [0, 0.8, 0.2] },
  APropDoorTriggerOnce: { col: [0, 0.5, 0.8] },
  APropDoorElectric: { col: [0.5, 0, 0.5] },
  APropSwitchPressure: { col: [0.5, 0.5, 0.0] },
  APropLever: { col: [0.7, 0.5, 0.1] },
  APropPlatform: { col: [0.5, 0.5, 0.5] },
  APropShakable: { col: [1, 0.5, 0.5] },
  APropTramp: { col: [0.85, 0.55, 0.2] },
  APropTrampPlatform: { col: [0.8, 0.6, 0.3] },
  APropWater: { col: [0.2, 0.5, 0.9] },
  APropSnapTo: { col: [0.5, 0.7, 0.7] },
  APropIgnitableBreakable: { col: [0.9, 0.3, 0.15] },
  APropSoundEmitter: { col: [0.4, 0.6, 1.0] },

  APickupDamageBoost: { col: [1, 0.75, 0], size: 1 },
  APickupPower: { col: [1, 0.5, 0] },
  APickupMegaPower: { col: [1, 0.25, 0] },
  APickupUnlimitedPower: { col: [1, 0, 0], size: 1 },
  APickupHealth: { col: [0.25, 1, 0.5] },
  APickupMegaHealth: { col: [0.25, 1, 0.25] },
  APickupUnlimitedHealth: { col: [0.25, 1, 0], size: 1 },
  APickupLife: { col: [0, 0.5, 0], size: 1 },
  APickupNickToken: { col: [1, 0.5, 0] },
  APickupNickTokenSilver: { col: [0.5, 0.5, 0.5] },
  APickupNickTokenGold: { col: [0.8, 0.8, 0.2], size: 1 },

  AWorldSectionVolume: { col: [1.0, 0.8, 1.0] },
  AWorldPropStatic: { col: [0.45, 0.35, 0.25] },
  AWorldPropAnimated: { col: [0.55, 0.45, 0.35] },
  ATeleportBlocker: { col: [1.0, 1.0, 0] },

  ASyndicateGrunt: { col: [0, 0.5, 0] },
  ASyndicateGruntW: { col: [0, 0.5, 0] },
  ASyndicateGruntBomber: { col: [0.5, 0, 0] },
  ASyndicateGruntMelee: { col: [0.4, 0.0, 0.2] },
  AGhostGuard: { col: [0.8, 0, 0] },
  AGhostGeneric: { col: [0.7, 0.2, 0.2] },
  AMiniFleabot: { col: [0.7, 0.5, 0.3] },
  APopper: { col: [0.5, 0.2, 0.6] },
  ADoomsdayTrooper: { col: [0.7, 0.1, 0.1] },
  ADoomsdayTrooperShielded: { col: [0.8, 0.2, 0.2] },
  APhaseSoldier: { col: [0.6, 0.1, 0.4] },
  ABarrier: { col: [0.6, 0.6, 0.9] },

  ALightAmbient: { col: [1.0, 0.95, 0.6] },
  ALightPointSource: { col: [1.0, 0.9, 0.4] },
  AFxGlow: { col: [1.0, 1.0, 0.7] },
  AFxTorch: { col: [1.0, 0.6, 0.2] },
  ADripEmitter: { col: [0.4, 0.6, 0.8] },
};

export function getStyle(type) {
  return STYLES[type] || STYLES.default;
}
