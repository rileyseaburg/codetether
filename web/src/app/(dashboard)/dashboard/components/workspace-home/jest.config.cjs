const root = require('node:path').resolve(__dirname, '../../../../../..')
const createJestConfig = require(require.resolve('next/jest', { paths: [root] }))({ dir: root })
module.exports = createJestConfig({
  rootDir: root,
  testEnvironment: 'jsdom',
  testEnvironmentOptions: { url: 'https://codetether.run' },
  testMatch: [__dirname + '/workspace-home.test.cjs'],
  moduleNameMapper: { '^@/(.*)$': '<rootDir>/src/$1' },
  setupFilesAfterEnv: ['@testing-library/jest-dom'],
  modulePathIgnorePatterns: ['<rootDir>/.next/'],
})