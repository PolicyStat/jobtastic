# jobtastic- Celery tasks plus more awesome

A [Celery](http://celeryproject.org) library
that makes your user-responsive long-running jobs
totally awesomer.
Celery is the awesome python job queueing tool
and jobtastic is a python library (plus javascript)
that brings some bells and whistles to the table
that you probably want if the results of your jobs are expensive
or if your users need to wait while they compute their results.

Jobtastic gives you goodies like:
* Easy progress estimation/reporting
* Job status feedback
* A jQuery plugin for easy client-side progress display
* Result caching
* [Thundering herd](http://en.wikipedia.org/wiki/Thundering_herd_problem) avoidance

Make your Celery jobs more awesome with Jobtastic.

## Why jobtastic?

If you have user-facing tasks that someone has to wait for
after they're triggered, you should try Jobtastic.
It's great for:
* Complex reports
* Graph generation
* CSV exports
* Any long-running, user-facing job

You could write all of the stuff yourself, but why?

## Installation

1. Get the project source and install it

    $ pip install jobtastic

## Creating Your First Task

## Client Side Handling

That's all well and good on the server side,
but the biggest benefit of jobtastic is useful user-facing feedback.
That means handling status checks using AJAX in the browser.

The easiest way to get rolling is to use our sister project,
[jquery-celery](https://github.com/PolicyStat/jquery-celery).
It contains jQuery plugins that help you:
* Poll for task status and handle the result
* Display a progress bar using the info from the `PROGRESS` state.
* Display tabular data using [DataTables](http://www.datatables.net/).

If you want to roll your own,
the general pattern is to poll a URL
(such as the django-celery
[task_status view](https://github.com/celery/django-celery/blob/master/djcelery/urls.py#L25) )
with your taskid to get JSON status information
and then handle the possible states to keep the user informed.

The [celery](https://github.com/PolicyStat/jquery-celery/blob/master/src/celery.js)
jQuery plugin might be a useful reference, if you're rolling your own.
In general, you'll want to handle the following cases:

### PENDING

Your task is still waiting for a worker process.
It's generally useful to display something like "Waiting for your task to begin".

### PROGRESS

Your task has started and you've got a JSON object like:

    {
        "progress_percent": 0,
        "time_remaining": 300
    }

`progress_percent` is a number between 0 and 100.
It's a good idea to give a different message if the percent is 0,
because the time remaining estimate might not yet be well-calibrated.

`time_remaining` is the number of seconds estimated to be left.
If there's no good estimate available, this value will be `-1`.

### SUCCESS

You've got your data. It's time to display the result.

### FAILURE

Something went wrong and the worker reported a failure.
This is a good time to either display a useful error message
(if the user can be expected to correct the problem),
or to ask the user to retry their task.

### Non-200 Request

There are occasions where requesting the task status itself might error out.
This isn't a reflection on the worker itself,
as it could be caused by any number of application errors.
In generally, you probably want to try again if this happens,
but if it persists, you'll want to give your user feedback.

## Is it Awesome?

Yes. Increasingly so.

# Non-affiliation

This project isn't affiliated with the awesome folks at the
[Celery Project](http://www.celeryproject.org).
It's a library that the folks at [PolicyStat](http://www.policystat.com)
have been using internally and decided to open source in the hopes it is useful to others.
