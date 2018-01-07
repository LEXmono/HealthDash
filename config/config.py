import boto3
from os import environ


class Config:
    """Class to load and or overwrite default settings."""
    APP_NAME = "Flask Health Dashboard"

    def __init__(self):
        self.stage = environ.get('FHD_STAGE', 'dev')

    def set_config(self, app):
        if self.stage == 'prod':
            # Prod Overrides

            # Force HTTPS verification for OAuth.
            environ['OAUTHLIB_INSECURE_TRANSPORT'] = '0'
            # Make sure Access Keys are set.
            if 'AWS_SECRET_ACCESS_KEY' and 'AWS_ACCESS_KEY_ID' in environ:
                pass
            else:
                raise Exception("Missing AWS Access Key and/or Key ID")

            # Get prod configuration file from S3
            # see /config/app.cfg for details
            s3 = boto3.resource('s3')
            obj = s3.Object(app.config['PROD_BUCKET'],
                            app.config['PROD_SECRET_KEY'])
            prod_config = obj.get()['Body'].read().decode('utf-8')
            options = dict(o.split('=') for o in prod_config.splitlines()
                           if '=' in o)
            for key, value in options.items():
                app.config.update(key=value)

            app.config.update(
                SQLALCHEMY_DATABASE_URI='sqlite:///' + app.root_path +
                                        '/fhd.db',
                SQLALCHEMY_MIGRATE_REPO = 'sqlite:///' + app.root_path +
                                          '/db_repository'
            )
        else:
            # Dev Overrides

            # When running locally, disable OAuthlib's HTTPs verification.
            environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

            app.config.update(
                SQLALCHEMY_DATABASE_URI='sqlite:///' + app.root_path +
                                        '/test.db',
                SQLALCHEMY_MIGRATE_REPO='sqlite:///' + app.root_path +
                                        '/test_db_repository'

            )
