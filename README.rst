Introduction
============

The idiotic distributed internet of things inhabitance controller
(idiotic) is a clusterable home automation controller that can combine
any number of disconnected home automation technologies into a single
unified inetrface. Inspired by `OpenHAB
<https://github.com/openhab/openhab>`__, idiotic aims to improve over
many of its shortcomings. Mostly, it's written in Python and all its
configuration is also just Python, so writing more advanced rules is
just as easy as writing simple ones and there's no convoluted syntax
to learn. Also, it's MIT licensed if you like that sort of thing.

Features
========

Disclaimer: idiotic is currently in alpha. It might break sometimes!
So far it has only tried to revolt once, but don't sue me if it goes
crazy and floods your house with coffee.

Uniform Configuration
---------------------

Every configuration file in idiotic is just a specialized Python
module. idiotic provides some basic building blocks that can easily
and clearly express many of the most common home automation
tasks, and does them using normal Python objects.

Lightweight and Modular
-----------------------

Because of the need for flexibility, idiotic's core does not contain
any technology-specific code. Instead, the core is just the scheduler
and some built-in generic items. Everything else is done in modules,
where you specify which real-world actions your items will have.

Declarative Rules
----------------------------------

idiotic supports defining declarative rules. These make it very easy
to avoid duplicating logic and keeping track of several conditions
independently. With a declarative rule, you define your logic and the
action it should take, and the rule takes care of updating the action
whenever the result of the logic changes.

::

    # This will let us reference our items and modules
    from idiotic import instance as c

    from idiotic.declare import Rule

    # Items have a 'w' attribute, short for 'watchers', which
    # lets us reference the watchable version of some attributes.
    # For basic items, 'state' is the main one you'll use.
    Rule(c.items.temperature.w.state >= 25,
         yes=lambda: print("Wow, it's super hot!"),
	 no=lambda: print("It's kind of okay."))


    # Scenes can be used in rules directly
    # We can make logic expressions with the bitwise operators
    Rule(c.scenes.house_occupied & ~c.scenes.daytime,
         yes=c.items.lights.on,
	 no=c.items.lights.off)

You can also use the simpler decorator-based rules.

::
    @bind(Change(c.items.temperature)
    def do_a_thing(event):
        if event.new > event.old:
	    print("It went up by " + (event.new - event.old))
	else:
	    print("It went down by " + (event.old - event.new))

Timer rules can be created, using `schedule
<https://github.com/dbader/schedule>`__ for nice friendly scheduling
syntax.

::
    @bind(Schedule(c.scheduler.every().tuesday.at('19:25')))
    def timer(event):
        print("It's 7:25!!!")
	c.items.lights.on()

Flexible Web-interface Creation
-------------------------------

With the built-in `idiotic-webui module
<https://github.com/idiotic/idiotic-webui>`__, you can create custom,
nice-looking, and powerful control panels without touching HTML or
Javascript.

Distributed Architecture
------------------------

*Danger! This is not quite done yet :(*

If you're planning on adding lots of sensors to your home or you're
stuck with some less-than-cooperative technologies, a Raspberry Pi
with some stuff plugged in the GPIO pins is about the best you can
get. That's why you can cluster idiotic across several devices.

REST API
--------

idiotic comes with an easily extensible REST API. It also has an
OpenHAB-compatible API, for backwards compatibility. 
