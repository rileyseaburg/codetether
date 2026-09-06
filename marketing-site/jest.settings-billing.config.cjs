const createJestConfig = require('next/jest')({ dir: './' })

module.exports = createJestConfig({
  testEnvironment: 'jsdom',
  testMatch: ['<rootDir>/tests/settings-billing.test.cjs'],
  modulePathIgnorePatterns: ['<rootDir>/.next/'],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
  setupFilesAfterEnv: ['@testing-library/jest-dom'],
})
