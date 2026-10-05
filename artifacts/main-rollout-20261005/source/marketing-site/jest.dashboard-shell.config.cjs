const createJestConfig = require('next/jest')({ dir: './' })

module.exports = createJestConfig({
  testEnvironment: 'jsdom',
  testMatch: [
    '<rootDir>/tests/dashboard-shell.test.cjs',
    '<rootDir>/tests/dashboard-preferences.test.cjs',
    '<rootDir>/tests/auth-readiness.test.cjs',
    '<rootDir>/tests/dashboard-navigation.test.cjs',
    '<rootDir>/tests/design-shell.test.cjs',
  ],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
  modulePathIgnorePatterns: ['<rootDir>/.next/'],
  setupFilesAfterEnv: ['@testing-library/jest-dom'],
})
