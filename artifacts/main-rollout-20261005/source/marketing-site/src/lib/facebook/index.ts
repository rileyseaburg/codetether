export {
    getAdAccount,
    listCampaigns,
    createCampaign,
    updateCampaignStatus,
    createAdSet,
    createVideoAdCreative,
    createAd,
    uploadVideoAsset,
    getVideoStatus,
    getCampaignInsights,
} from './client';
export type { FacebookAdAccount, FacebookCampaign, FacebookAdSet } from './client';

export {
    launchFacebookVideoAd,
    checkFacebookVideoStatus,
    getFacebookVideoReport,
} from './videoAds';
export type {
    LaunchFacebookVideoAdParams,
    LaunchFacebookVideoAdResult,
} from './videoAds';
