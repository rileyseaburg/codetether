/**
 * CodeTether Google Ads Integration
 *
 * Barrel export for all Google Ads modules.
 *
 * @module lib/google
 */

export {
    getCustomer,
    listCampaigns,
    getCampaign,
    createCampaign,
    updateCampaignStatus,
    updateCampaignBudget,
    listAdGroups,
    createAdGroup,
    updateAdGroupBid,
    createResponsiveSearchAd,
    listAds,
    addKeywords,
    addNegativeKeywords,
    dollarsToMicros,
    microsToDollars,
    centsToMicros,
    microsToCents,
    enums,
} from './client';

export {
    getCampaignReport,
    getAdGroupReport,
    getSearchTermsReport,
    getAccountSummary,
    getCampaignMetricsForOptimizer,
} from './reporting';
export type {
    CampaignMetrics,
    AdGroupMetrics,
    SearchTermMetrics,
    AccountSummary,
} from './reporting';

export {
    uploadConversions,
    trackCodetetherConversion,
    listConversionActions,
} from './conversions';
export type { ConversionUpload, ConversionResult } from './conversions';

export {
    syncGoogleAdsToAdBrain,
    applyOptimizationToGoogleAds,
    runFullSyncCycle,
} from './sync';
export type { SyncResult } from './sync';

export {
    uploadYouTubeAsset,
    getAssetDetails,
    createVideoCampaign,
    createVideoAdGroup,
    createInStreamVideoAd,
    createBumperVideoAd,
    listVideoAds,
    getVideoReport,
    attachAudienceToAdGroup,
    launchVideoAdFromYouTube,
} from './videoAds';
