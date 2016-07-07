"""Command line interface for chalice.

Contains commands for deploying chalice.

"""
import os
import json
import datetime

import click
import botocore.exceptions

from chalice import deployer

TEMPLATE_APP = """\
from chalice import Chalice

app = Chalice(app_name='%s')


@app.route('/')
def index():
    return {'hello': 'world'}

"""


def show_lambda_logs(config, max_entries, include_lambda_messages):
    shown = 0
    import boto3
    from chalice import logs
    lambda_arn = config['config']['lambda_arn']
    client = boto3.client('logs')
    retriever = logs.LogRetriever.create_from_arn(client, lambda_arn)
    events = retriever.retrieve_logs(
        include_lambda_messages=include_lambda_messages,
        max_entries=max_entries)
    for event in events:
        print event['timestamp'], event['logShortId'], event['message'].strip()


def load_project_config(project_dir):
    """Load the chalice config file from the project directory.

    :raise: OSError/IOError if unable to load the config file.

    """
    config_file = os.path.join(project_dir, '.chalice', 'config.json')
    with open(config_file) as f:
        return json.loads(f.read())


def load_chalice_app(project_dir):
    app_py = os.path.join(project_dir, 'app.py')
    with open(app_py) as f:
        g = {}
        contents = f.read()
        exec contents in g
        return g['app']


@click.group()
@click.pass_context
def cli(ctx):
    pass


@cli.command()
@click.pass_context
def local(ctx):
    click.echo("Local command")


@cli.command()
@click.option('--project-dir',
              help='The project directory.  Defaults to CWD')
@click.argument('stage', nargs=1, required=False)
@click.pass_context
def deploy(ctx, project_dir, stage):
    if project_dir is None:
        project_dir = os.getcwd()
    ctx.obj['project_dir'] = project_dir
    os.chdir(project_dir)
    try:
        config = load_project_config(project_dir)
        ctx.obj['config'] = config
    except (OSError, IOError):
        click.echo("Unable to load the project config file. "
                   "Are you sure this is a chalice project?")
        raise click.Abort()
    if stage is not None:
        config['stage'] = stage
    app_obj = load_chalice_app(project_dir)
    ctx.obj['chalice_app'] = app_obj
    d = deployer.Deployer()
    try:
        d.deploy(ctx.obj)
    except botocore.exceptions.NoRegionError:
        e = click.ClickException("No region configured. "
                                 "Either export the AWS_DEFAULT_REGION "
                                 "environment variable or set the "
                                 "region value in our ~/.aws/config file.")
        e.exit_code = 2
        raise e


@cli.command()
@click.option('--project-dir',
              help='The project directory.  Defaults to CWD')
@click.option('--num-entries', default=None, type=int,
              help='Max number of log entries to show.')
@click.option('--include-lambda-messages/--no-include-lambda-messages',
              default=True,
              help='Controls whether or not lambda log messages are included.')
@click.pass_context
def logs(ctx, project_dir, num_entries, include_lambda_messages):
    if project_dir is None:
        project_dir = os.getcwd()
    ctx.obj['project_dir'] = project_dir
    os.chdir(project_dir)
    try:
        config = load_project_config(project_dir)
        ctx.obj['config'] = config
    except (OSError, IOError):
        click.echo("Unable to load the project config file. "
                   "Are you sure this is a chalice project?")
        raise click.Abort()
    app_obj = load_chalice_app(project_dir)
    ctx.obj['chalice_app'] = app_obj
    show_lambda_logs(ctx.obj, num_entries, include_lambda_messages)


@cli.command('new-project')
@click.argument('project_name')
@click.pass_context
def new_project(ctx, project_name):
    if os.path.isdir(project_name):
        click.echo("Directory already exists: %s" % project_name)
        raise click.Abort()
    chalice_dir = os.path.join(project_name, '.chalice')
    os.makedirs(chalice_dir)
    config = os.path.join(project_name, '.chalice', 'config.json')
    with open(config, 'w') as f:
        f.write(json.dumps({'app_name': project_name,
                            'stage': 'dev'}, indent=2))
    with open(os.path.join(project_name, 'requirements.txt'), 'w') as f:
        pass
    with open(os.path.join(project_name, 'app.py'), 'w') as f:
        f.write(TEMPLATE_APP % project_name)


def main():
    # click's dynamic attrs will allow us to pass through
    # 'obj' via the context object, so we're ignoring
    # these error messages from pylint because we know it's ok.
    # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
    return cli(obj={})