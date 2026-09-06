const createJestConfig = require('next/jest')({ dir: './' })

module.exports = createJestConfig({
  testEnvironment: 'jsdom',
  testMatch: ['<rootDir>/tests/tasks-resilience.test.cjs'],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
  modulePathIgnorePatterns: ['<rootDir>/.next/'],
  setupFilesAfterEnv: ['@testing-library/jest-dom'],
})
