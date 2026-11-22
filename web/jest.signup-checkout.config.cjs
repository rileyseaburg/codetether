const createJestConfig = require('next/jest')({ dir: './' })

module.exports = createJestConfig({
  testEnvironment: 'jsdom',
  testEnvironmentOptions: { url: 'https://codetether.run/' },
  testMatch: ['<rootDir>/tests/signup-checkout.test.cjs'],
  modulePathIgnorePatterns: ['<rootDir>/.next/'],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
  setupFilesAfterEnv: ['@testing-library/jest-dom'],
})
