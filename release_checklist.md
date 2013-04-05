# Things to do in order to cut a new release

## Passing Tests

Make sure that all of the tests on travis-ci have run and are passing.

## Bump the version

Editing `jobtastic/__init__.py` and increment the version
according to the [Semantic Versioning](http://semver.org/) standard.

## Changelog

Ensure that the `CHANGELOG.rst` file includes all relevant changes.

## Documentation is up to date

Ensure that any new features are documented
and give the docs a read-through
to make sure they haven't started lying.

## Publish documentation

We currently use Github Pages as both
the project home page
and the place for online documentation.

1. Visit the [automatic page generator](https://github.com/PolicyStat/jobtastic/generated_pages/new).
1. Click `Load README.md` to update the content.
1. Click `Continue to Layouts`
1. Select the "Leap Day" theme and scan to make sure it looks good.
1. Click `Publish`.

## Build and push the package to PyPi

1. Run `$ python setup.py sdist` to make sure the package is kosher.
  Correct any errors or warnings that appear and commit those changes.
1. Check the package file to ensure that it has the files we want.
1. Push to PyPi! `$ python setup.py sdist upload`

## Tag the version

Use git to tag the version according to
the[Semantic Versioning](http://semver.org/) standard.

eg. `$ git tag v0.1.1 && git push --tags`

## Consider announcing things

If the new version adds something sufficiently cool,
consider posting to the celery mailing list.
Also consider posting to G+, Twitter, etc.
so that folks who would find Jobtastic useful can actually find it.
