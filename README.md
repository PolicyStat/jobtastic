# jobtastic- Celery tasks plus more awesome

[![Build Status](https://travis-ci.org/PolicyStat/jobtastic.png?branch=master)](https://travis-ci.org/PolicyStat/jobtastic)

Jobtastic makes your user-responsive long-running
[Celery](http://celeryproject.org) jobs totally awesomer.
Celery is the ubiquitous python job queueing tool
and jobtastic is a python library
that adds useful features to your Celery tasks.
Specifically, these are features you probably want
if the results of your jobs are expensive
or if your users need to wait while they compute their results.

Jobtastic gives you goodies like:
* Easy progress estimation/reporting
* Job status feedback
* Helper methods for gracefully handling a dead task broker
  (`delay_or_eager` and `delay_or_fail`)
* Super-easy result caching
* [Thundering herd](http://en.wikipedia.org/wiki/Thundering_herd_problem) avoidance
* Integration with a
  [celery jQuery plugin](https://github.com/PolicyStat/jquery-celery)
  for easy client-side progress display
* Memory leak detection in a task run

Make your Celery jobs more awesome with Jobtastic.

## Why Jobtastic?

If you have user-facing tasks for which a user must wait,
you should try Jobtastic.
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

Let's take a look at an example task using Jobtastic:

``` python
from time import sleep

from jobtastic import JobtasticTask

class LotsOfDivisionTask(JobtasticTask):
	"""
	Division is hard. Make Celery do it a bunch.
	"""
	# These are the Task kwargs that matter for caching purposes
	significant_kwargs = [
		('numerators', str),
		('denominators', str),
	]
	# How long should we give a task before assuming it has failed?
	herd_avoidance_timeout = 60  # Shouldn't take more than 60 seconds
	# How long we want to cache results with identical ``significant_kwargs``
	cache_duration = 0  # Cache these results forever. Math is pretty stable.
	# Note: 0 means different things in different cache backends. RTFM for yours.

	def calculate_result(self, numerators, denominators, **kwargs):
		"""
		MATH!!!
		"""
		results = []
		divisions_to_do = len(numerators)
		# Only actually update the progress in the backend every 10 operations
		update_frequency = 10
		for count, divisors in enumerate(zip(numerators, denominators)):
			numerator, denominator = divisors
			results.append(numerator / denominator)
			# Let's let everyone know how we're doing
			self.update_progress(
                count,
                divisions_to_do,
                update_frequency=update_frequency,
            )
			# Let's pretend that we're using the computers that landed us on the moon
			sleep(0.1)

		return results
```

This task is very trivial,
but imagine doing something time-consuming instead of division
(or just a ton of division)
while a user waited.
We wouldn't want a double-clicker to cause this to happen twice concurrently,
we wouldn't want to ever redo this work on the same numbers
and we would want the user to have at least some idea
of how long they'll need to wait.
Just by setting those 3 member variables,
we've done all of these things.

Basically, creating a Celery task using Jobtastic is a matter of:

1. Subclassing `jobtastic.JobtasticTask`
2. Defining some required member variables
3. Writing your `calculate_result` method
  (instead of the normal Celery `run()` method)
4. Sprinkling `update_progress()` calls in your `calculate_result()` method
  to communicate progress

Now, to use this task in your Django view, you'll do something like:

``` python
from django.shortcuts import render_to_response

from my_app.tasks import LotsOfDivisionTask

def lets_divide(request):
	"""
	Do a set number of divisions and keep the user up to date on progress.
	"""
	iterations = request.GET.get('iterations', 1000)  # That's a lot. Right?
	step = 10

	# If we can't connect to the backend, let's not just 500. k?
	result = LotsOfDivisionTask.delay_or_fail(
		numerators=range(0, step * iterations * 2, step * 2),
		denominators=range(1, step * iterations, step),
	)

	return render_to_response(
		'my_app/lets_divide.html',
		{'task_id': result.task_id},
	)
```

The `my_app/lets_divide.html` template will then use the `task_id`
to query the task result all asynchronous-like
and keep the user up to date with what is happening.

For [Flask](http://flask.pocoo.org/), you might do something like:

``` python
from flask import Flask, render_template

from my_app.tasks import LotsOfDivisionTask

app = Flask(__name__)

@app.route("/", methods=['GET'])
def lets_divide():
	iterations = request.args.get('iterations', 1000)
	step = 10

	result = LotsOfDivisionTask.delay_or_fail(
		numerators=range(0, step * iterations * 2, step * 2),
		denominators=range(1, step * iterations, step),
	)

	return render_template('my_app/lets_divide.html', task_id=request.task_id)
```

### Required Member Variables

"But wait, Wes. What the heck do those member variables actually do?" You ask.

Firstly. How the heck did you know my name?

And B, why don't I tell you!?

#### significant_kwargs

This is key to your caching magic.
It's a list of 2-tuples containing the name of a kwarg
plus a function to turn that kwarg in to a string.
Jobtastic uses these to determine if your task
should have an identical result to another task run.
In our division example,
any task with the same numerators and denominators can be considered identical,
so Jobtastic can do smart things.

``` python
significant_kwargs = [
	('numerators', str),
	('denominators', str),
]
```

If we were living in bizzaro world,
and only the numerators mattered for division results,
we could do something like:

``` python
significant_kwargs = [
	('numerators', str),
]
```

Now tasks called with an identical list of numerators will share a result.

#### herd_avoidance_timeout

This is the max number of seconds for which Jobtastic will wait
for identical task results to be determined.
You want this number to be on the very high end
of the amount of time you expect to wait
(after a task starts)
for the result.
If this number is hit,
it's assumed that something bad happened to the other task run
(a worker failed)
and we'll start calculating from the start.

### Optional Member Variables

These let you tweak the default behavior.
Most often, you'll just be setting the `cache_duration`
to enable result caching.

#### cache_duration

If you want your results cached,
set this to a non-negative number of seconds.
This is the number of seconds for which identical jobs
should try to just re-use the cached result.
The default is -1,
meaning don't do any caching.
Remember,
`JobtasticTask` uses your `signficant_kwargs` to determine what is identical.

#### cache_prefix

This is an optional string used to represent tasks
that should share cache results and thundering herd avoidance.
You should almost never set this yourself,
and instead should let Jobtastic use the `module.class` name.
If you have two different tasks that should share caching,
or you have some very-odd cache key conflict,
then you can change this yourself.
You probably don't need to.

#### memleak_threshold

Set this value to monitor your tasks
for any runs that increase the memory usage
by more than this number of Megabytes
(the SI definition).
Individual task runs that increase resident memory
by more than this threshold
get some extra logging
in order to help you debug the problem.
By default, it logs the following via standard Celery logging:
 * The memory increase
 * The memory starting value
 * The memory ending value
 * The task's kwargs

If you'd like to customize this behavior,
you can override the `warn_of_memory_leak` method in your own `Task`.

### Method to Override

Other than tweaking the member variables,
you'll probably want to actually, you know,
*do something* in your task.

#### calculate_result

This is where your magic happens.
Do work here and return the result.

You'll almost definitely want to
call `update_progress` periodically in this method
so that your users get an idea of for how long they'll be waiting.

### Progress feedback helper

This is the guy you'll want to call
to provide nice progress feedback and estimation.

#### update_progress

In your `calculate_result`,
you'll want to periodically make calls like:

``` python
self.update_progress(work_done, total_work_to_do)
```

Jobtastic takes care of handling timers to give estimates,
and assumes that progress will be roughly uniform across each work item.

Most of the time,
you really don't need ultra-granular progress updates
and can afford to only give an update every `N` items completed.
Since every update would potentially hit your
[CELERY_RESULT_BACKEND](http://celery.github.com/celery/configuration.html#celery-result-backend),
and that might cause a network trip,
it's probably a good idea to use the optional `update_frequency` argument
so that Jobtastic doesn't swamp your backend
with updated estimates no user will ever see.

In our division example,
we're only actually updating the progress every 10 division operations:

``` python
# Only actually update the progress in the backend every 10 operations
update_frequency = 10
for count, divisors in enumerate(zip(numerators, denominators)):
	numerator, denominator = divisors
	results.append(numerator / denominator)
	# Let's let everyone know how we're doing
	self.update_progress(count, divisions_to_do, update_frequency=10)
```

## Using your JobtasticTask

Sometimes,
your [Task Broker](http://celery.github.com/celery/configuration.html#broker-url)
just up and dies
(I'm looking at you, old versions of RabbitMQ).
In production,
calling straight up `delay()` with a dead backend
will throw an error that varies based on what backend you're actually using.
You probably don't want to just give your user a generic 500 page
if your broker is down,
and it's not fun to handle that exception every single place
you might use Celery.
Jobtastic has your back.

Included are `delay_or_eager` and `delay_or_fail` methods
that handle a dead backend
and do something a little more production-friendly.

Note: One very important caveat with `JobtasticTask` is that
all of your arguments must be keyword arguments.

Note: This is a limitation of the current `signficant_kwargs` implementation,
and totally fixable if someone wants to submit a pull request.

### delay_or_eager

If your broker is behaving itself,
this guy acts just like `delay()`.
In the case that your broker is down,
though,
it just goes ahead and runs the task in the current process
and skips sending the task to a worker.
You get back a nice shiny `EagerResult` object,
which behaves just like the `AsyncResult` you were expecting.
If you have a task that realistically only takes a few seconds to run,
this might be better than giving yours users an error message.

### delay_or_fail

Like `delay_or_eager`,
this helps you handle a dead broker.
Instead of running your task in the current process,
this actually generates a task result representing the failure.
This means that your client-side code can handle it
like any other failed task
and do something nice for the user.
Maybe send them a fruit basket?

For tasks that might take a while
or consume a lot of RAM,
you're probably better off using this than `delay_or_eager`
because you don't want to make a resource problem worse.

## Client Side Handling

That's all well and good on the server side,
but the biggest benefit of Jobtastic is useful user-facing feedback.
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

The [jquery-celery](https://github.com/PolicyStat/jquery-celery/blob/master/src/celery.js)
jQuery plugin might still be useful as reference,
even if you're rolling your own.
In general, you'll want to handle the following cases:

### PENDING

Your task is still waiting for a worker process.
It's generally useful to display something like "Waiting for your task to begin".

### PROGRESS

Your task has started and you've got a JSON object like:

``` javascript
{
	"progress_percent": 0,
	"time_remaining": 300
}
```

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
In general, you probably want to try again if this happens,
but if it persists, you'll want to give your user feedback.

## Running The Test Suite

You can run Jobtastic's test suite yourself via:

    $ python setup.py test

Our test suite currently only tests usage with Django,
which is definitely a [bug](https://github.com/PolicyStat/jobtastic/issues/15).
Especially if you use Jobtastic with Flask,
we would love a pull request.

You can also run tests
across all of our supported python/Django/Celery versions via Tox:

    $ tox

## Is it Awesome?

Yes. Increasingly so.

## Project Status

Jobtastic is currently known to work
with Django 1.3-1.5 and Celery 2.5-3.0.
The goal is to support those versions and newer.
Please file issues if there are problems
with newer versions of Django/Celery.

### A note on usage with Flask

If you're using Flask instead of Django,
then the only currently-supported way to work with Jobtastic
is with Memcached as your `CELERY_RESULT_BACKEND`.
A more generally-pythonic way of choosing/plugging cache backends
is definitely a goal,
though,
and pull requests
(see [Issue 8](https://github.com/PolicyStat/jobtastic/issues/8) )
or suggestions are very welcome.
We'd also love some Flask-specific tests!

## Non-affiliation

This project isn't affiliated with the awesome folks at the
[Celery Project](http://www.celeryproject.org)
(unless having a huge crush counts as affiliation).
It's a library that the folks at [PolicyStat](http://www.policystat.com)
have been using internally
and decided to open source in the hopes it is useful to others.
