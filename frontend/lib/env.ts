const requiredPublicEnv = {
  NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL
};

export function getPublicEnv() {
  if (!requiredPublicEnv.NEXT_PUBLIC_API_BASE_URL) {
    throw new Error('Missing NEXT_PUBLIC_API_BASE_URL. Add it to your Amplify environment settings.');
  }

  return {
    apiBaseUrl: requiredPublicEnv.NEXT_PUBLIC_API_BASE_URL
  };
}
